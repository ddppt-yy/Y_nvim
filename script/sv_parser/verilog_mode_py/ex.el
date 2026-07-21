;;; ex.el --- Dump verilog-mode AUTO connectivity reports -*- lexical-binding: t; -*-

;; Load the sibling verilog-mode.el when this file is used standalone.
(let* ((here (file-name-directory (or load-file-name buffer-file-name default-directory)))
       (local-verilog-mode (and here (expand-file-name "verilog-mode.el" here))))
  (when (and (not (featurep 'verilog-mode))
             local-verilog-mode
             (file-readable-p local-verilog-mode))
    (load-file local-verilog-mode)))

(require 'verilog-mode)
(require 'json)
(require 'seq)
(require 'subr-x)

(defvar vm-auto-report-run-auto t
  "Non-nil means `vm-dump-auto' runs `verilog-auto' before reporting.")

(defvar vm-auto-report-pretty-json t
  "Non-nil means `vm-dump-auto' writes formatted JSON.")

(defvar vm-auto-report-include-unresolved-instances t
  "Non-nil means report hand-parsed instances even when their module is unresolved.")

(defvar vm-auto-report-write-text-files t
  "Non-nil means `vm-dump-auto' also writes signal.txt and unconnect.txt.")

(defconst vm-auto-report--auto-re
  "\\(/\\*AUTOINST\\((.*?)\\)?\\*/\\|\\.\\*\\)"
  "Regexp matching AUTOINST markers that verilog-mode expands.")

(defconst vm-auto-report--defun-re
  "\\<\\(macromodule\\|connectmodule\\|module\\|program\\|interface\\)\\>"
  "Regexp matching design units reported by this script.")

(defun vm-auto-report--vector (items)
  "Return ITEMS as a JSON array."
  (vconcat items))

(defun vm-auto-report--json (object)
  "Encode OBJECT as JSON."
  (let ((json-encoding-pretty-print vm-auto-report-pretty-json))
    (json-encode object)))

(defun vm-auto-report--maybe-string (value)
  "Return VALUE when it is a string, else nil."
  (and (stringp value) value))

(defun vm-auto-report--location (pos)
  "Return an alist describing POS in the current buffer."
  (save-excursion
    (goto-char pos)
    `((line . ,(line-number-at-pos pos))
      (column . ,(current-column)))))

(defun vm-auto-report--sig (direction sig)
  "Return a JSON-ready description of SIG with DIRECTION."
  `((direction . ,direction)
    (name . ,(verilog-sig-name sig))
    (bits . ,(vm-auto-report--maybe-string (verilog-sig-bits sig)))
    (multidim . ,(vm-auto-report--maybe-string (verilog-sig-multidim-string sig)))
    (memory . ,(vm-auto-report--maybe-string (verilog-sig-memory sig)))
    (signed . ,(and (verilog-sig-signed sig) t))
    (type . ,(vm-auto-report--maybe-string (verilog-sig-type sig)))
    (modport . ,(vm-auto-report--maybe-string (verilog-sig-modport sig)))
    (comment . ,(vm-auto-report--maybe-string (verilog-sig-comment sig)))))

(defun vm-auto-report--sig-list (direction signals)
  "Return SIGNALS encoded as JSON-ready entries with DIRECTION."
  (vm-auto-report--vector
   (mapcar (lambda (sig) (vm-auto-report--sig direction sig)) signals)))

(defun vm-auto-report--auto-signals (modi)
  "Return aggregate AUTO-connected signals for MODI."
  (let ((subdecls (condition-case nil
                      (verilog-modi-get-sub-decls modi)
                    (error nil))))
    `((outputs . ,(vm-auto-report--sig-list
                   "output"
                   (and subdecls (verilog-subdecls-get-outputs subdecls))))
      (inputs . ,(vm-auto-report--sig-list
                  "input"
                  (and subdecls (verilog-subdecls-get-inputs subdecls))))
      (inouts . ,(vm-auto-report--sig-list
                  "inout"
                  (and subdecls (verilog-subdecls-get-inouts subdecls))))
      (interfaces . ,(vm-auto-report--sig-list
                      "interface"
                      (and subdecls (verilog-subdecls-get-interfaces subdecls))))
      (interfaced . ,(vm-auto-report--sig-list
                      "interfaced"
                      (and subdecls (verilog-subdecls-get-interfaced subdecls)))))))

(defun vm-auto-report--lookup-module (module)
  "Return the verilog-mode modi for MODULE, or nil."
  (condition-case nil
      (verilog-modi-lookup module t t)
    (error nil)))

(defun vm-auto-report--module-file (modi)
  "Return the resolved file path for MODI, or nil."
  (and modi
       (let ((filename (verilog-modi-filename modi)))
         (and (stringp filename) (expand-file-name filename)))))

(defun vm-auto-report--portdata-direction (port decls)
  "Return direction and portdata for PORT in DECLS."
  (cond ((assoc port (verilog-decls-get-outputs decls))
         (cons "output" (assoc port (verilog-decls-get-outputs decls))))
        ((assoc port (verilog-decls-get-inputs decls))
         (cons "input" (assoc port (verilog-decls-get-inputs decls))))
        ((assoc port (verilog-decls-get-inouts decls))
         (cons "inout" (assoc port (verilog-decls-get-inouts decls))))
        ((assoc port (verilog-decls-get-interfaces decls))
         (cons "interface" (assoc port (verilog-decls-get-interfaces decls))))
        ((assoc port (verilog-decls-get-vars decls))
         (cons "interfaced" (assoc port (verilog-decls-get-vars decls))))))

(defun vm-auto-report--connection (section port expr submod-decls)
  "Return a JSON-ready connection entry."
  (let* ((found (and submod-decls
                     (vm-auto-report--portdata-direction port submod-decls)))
         (direction (or section (car found)))
         (portdata (cdr found)))
    `((direction . ,direction)
      (port . ,port)
      (expr . ,expr)
      (bits . ,(and portdata (vm-auto-report--maybe-string (verilog-sig-bits portdata))))
      (multidim . ,(and portdata (vm-auto-report--maybe-string
                                   (verilog-sig-multidim-string portdata))))
      (memory . ,(and portdata (vm-auto-report--maybe-string (verilog-sig-memory portdata))))
      (signed . ,(and portdata (verilog-sig-signed portdata) t))
      (type . ,(and portdata (vm-auto-report--maybe-string (verilog-sig-type portdata))))
      (modport . ,(and portdata (vm-auto-report--maybe-string
                                  (verilog-sig-modport portdata)))))))

(defun vm-auto-report--alist-get (key alist)
  "Return KEY from ALIST using `eq' for key comparison."
  (cdr (assq key alist)))

(defun vm-auto-report--items (value)
  "Return VALUE as a list, accepting vectors used for JSON arrays."
  (cond ((vectorp value) (append value nil))
        ((listp value) value)
        (t nil)))

(defun vm-auto-report--port-entry (direction sig reason)
  "Return a JSON-ready unconnected port entry for SIG."
  `((direction . ,direction)
    (port . ,(verilog-sig-name sig))
    (name . ,(verilog-sig-name sig))
    (reason . ,reason)
    (bits . ,(vm-auto-report--maybe-string (verilog-sig-bits sig)))
    (multidim . ,(vm-auto-report--maybe-string (verilog-sig-multidim-string sig)))
    (memory . ,(vm-auto-report--maybe-string (verilog-sig-memory sig)))
    (signed . ,(and (verilog-sig-signed sig) t))
    (type . ,(vm-auto-report--maybe-string (verilog-sig-type sig)))
    (modport . ,(vm-auto-report--maybe-string (verilog-sig-modport sig)))))

(defun vm-auto-report--decl-port-alist (decls)
  "Return all submodule ports from DECLS as (name direction sig)."
  (append
   (mapcar (lambda (sig) (list (verilog-sig-name sig) "output" sig))
           (verilog-decls-get-outputs decls))
   (mapcar (lambda (sig) (list (verilog-sig-name sig) "inout" sig))
           (verilog-decls-get-inouts decls))
   (mapcar (lambda (sig) (list (verilog-sig-name sig) "input" sig))
           (verilog-decls-get-inputs decls))
   (mapcar (lambda (sig) (list (verilog-sig-name sig) "interface" sig))
           (verilog-decls-get-interfaces decls))))

(defun vm-auto-report--ordered-decl-ports (decls port-order)
  "Return declaration ports from DECLS ordered by PORT-ORDER when available."
  (let ((ports (vm-auto-report--decl-port-alist decls))
        ordered seen rest)
    (dolist (name port-order)
      (let ((entry (assoc name ports)))
        (when entry
          (push entry ordered)
          (push (car entry) seen))))
    (dolist (entry ports)
      (unless (member (car entry) seen)
        (push entry rest)))
    (append (nreverse ordered) (nreverse rest))))

(defun vm-auto-report--port-order-from-modi (modi)
  "Return the declared port order for MODI, best effort."
  (when modi
    (condition-case nil
        (save-excursion
          (verilog-modi-goto modi)
          (let ((open (and (eq (char-before) ?\() (1- (point))))
                close names)
            (when open
              (goto-char open)
              (setq close (vm-auto-report--sexp-end-at-point))
              (when close
                (goto-char (1+ open))
                (while (< (point) (1- close))
                  (let ((start (point))
                        end segment name)
                    (setq end (vm-auto-report--connection-end (1- close)))
                    (setq segment (buffer-substring-no-properties start end))
                    (setq name (vm-auto-report--port-name-from-header-segment segment))
                    (when name
                      (push name names))
                    (when (looking-at ",")
                      (forward-char 1))))
                (nreverse names)))))
      (error nil))))

(defun vm-auto-report--port-name-from-header-segment (segment)
  "Return the port name represented by a module header SEGMENT."
  (let ((start 0)
        names name)
    (while (string-match "\\([a-zA-Z_$][a-zA-Z0-9_$]*\\|\\\\[^ \t\n\f]+\\s-\\)" segment start)
      (setq name (match-string 1 segment))
      (setq start (match-end 0))
      (unless (or (member name verilog-keywords)
                  (member name '("signed" "unsigned" "wire" "reg" "logic"
                                 "bit" "tri" "input" "output" "inout"
                                 "parameter" "localparam")))
        (push name names)))
    (car names)))

(defun vm-auto-report--connection-dot-star-p (connections)
  "Return non-nil if CONNECTIONS contains a .*-style connection."
  (let ((found nil))
    (dolist (conn (append connections nil))
      (when (equal (vm-auto-report--alist-get 'style conn) "dot-star")
        (setq found t)))
    found))

(defun vm-auto-report--connection-port-state (connections)
  "Return (connected empty) port-name lists from CONNECTIONS."
  (let (connected empty)
    (dolist (conn (append connections nil))
      (let ((port (vm-auto-report--alist-get 'port conn))
            (expr (vm-auto-report--alist-get 'expr conn))
            (style (vm-auto-report--alist-get 'style conn)))
        (when (and port
                   (not (equal port "*"))
                   (member style '("named" "dot-name" "ordered")))
          (if (or (not expr) (string-empty-p expr))
              (push port empty)
            (push port connected)))))
    (list connected empty)))

(defun vm-auto-report--wildcard-dot-star-p (conn)
  "Return non-nil when CONN is the raw .* wildcard entry."
  (and (equal (vm-auto-report--alist-get 'style conn) "dot-star")
       (equal (vm-auto-report--alist-get 'port conn) "*")))

(defun vm-auto-report--connection-from-port-entry (entry)
  "Return a dot-star connection entry from a declared port ENTRY."
  (let ((name (nth 0 entry))
        (direction (nth 1 entry))
        (sig (nth 2 entry)))
    `((style . "dot-star")
      (direction . ,direction)
      (port . ,name)
      (expr . ,name)
      (bits . ,(vm-auto-report--maybe-string (verilog-sig-bits sig)))
      (multidim . ,(vm-auto-report--maybe-string
                     (verilog-sig-multidim-string sig)))
      (memory . ,(vm-auto-report--maybe-string (verilog-sig-memory sig)))
      (signed . ,(and (verilog-sig-signed sig) t))
      (type . ,(vm-auto-report--maybe-string (verilog-sig-type sig)))
      (modport . ,(vm-auto-report--maybe-string
                    (verilog-sig-modport sig))))))

(defun vm-auto-report--expand-dot-star-with-decls
    (connections submod-decls port-order)
  "Expand raw .*-style CONNECTIONS using SUBMOD-DECLS and PORT-ORDER."
  (let* ((items (vm-auto-report--items connections))
         (state (vm-auto-report--connection-port-state items))
         (mentioned (append (nth 0 state) (nth 1 state)))
         explicit has-dot-star)
    (dolist (conn items)
      (if (vm-auto-report--wildcard-dot-star-p conn)
          (setq has-dot-star t)
        (push conn explicit)))
    (if (not has-dot-star)
        items
      (let (implicit)
        (if submod-decls
            (progn
              (dolist (entry (vm-auto-report--ordered-decl-ports
                              submod-decls port-order))
                (unless (member (nth 0 entry) mentioned)
                  (push (vm-auto-report--connection-from-port-entry entry)
                        implicit)))
              (append (nreverse explicit) (nreverse implicit)))
          items)))))

(defun vm-auto-report--unconnected-ports (submod-decls connections port-order)
  "Return ports from SUBMOD-DECLS not connected by CONNECTIONS."
  (if (not submod-decls)
      (vm-auto-report--vector nil)
    (let* ((state (vm-auto-report--connection-port-state connections))
           (connected (nth 0 state))
           (empty (nth 1 state))
           (dot-star (vm-auto-report--connection-dot-star-p connections))
           unconnected)
      (dolist (entry (vm-auto-report--ordered-decl-ports submod-decls port-order))
        (let ((name (nth 0 entry))
              (direction (nth 1 entry))
              (sig (nth 2 entry)))
          (cond ((member name empty)
                 (push (vm-auto-report--port-entry direction sig "empty")
                       unconnected))
                ((or dot-star (member name connected))
                 nil)
                (t
                 (push (vm-auto-report--port-entry direction sig "omitted")
                       unconnected)))))
      (vm-auto-report--vector (nreverse unconnected)))))

(defun vm-auto-report--section-direction ()
  "Return the AUTOINST section direction at point, or nil."
  (cond ((looking-at "\\s-*//\\s-*Outputs\\b") "output")
        ((looking-at "\\s-*//\\s-*Inputs\\b") "input")
        ((looking-at "\\s-*//\\s-*Inouts\\b") "inout")
        ((looking-at "\\s-*//\\s-*Interfaces\\b") "interface")
        ((looking-at "\\s-*//\\s-*Interfaced\\b") "interfaced")))

(defun vm-auto-report--read-connection-line (section submod-decls)
  "Read one generated AUTOINST connection line at point."
  (save-excursion
    (when (and section
               (not (verilog-inside-comment-or-string-p))
               (looking-at "\\s-*\\.\\s-*\\([^ \t\n\f,(]+\\)\\s-*"))
      (let ((port (match-string-no-properties 1))
            expr)
        (goto-char (match-end 0))
        (skip-chars-forward " \t\n\f")
        (setq expr
              (cond ((looking-at "(")
                     (let ((start (1+ (point)))
                           (end (save-excursion
                                  (verilog-forward-sexp-ign-cmt 1)
                                  (1- (point)))))
                       (string-trim
                        (buffer-substring-no-properties start end))))
                    (t port)))
        (vm-auto-report--connection section port expr submod-decls)))))

(defun vm-auto-report--generated-connections (marker-end inst-end submod-decls)
  "Return generated AUTOINST connections between MARKER-END and INST-END."
  (let (section connections)
    (save-excursion
      (goto-char marker-end)
      (while (< (point) inst-end)
        (beginning-of-line)
        (when (< (point) inst-end)
          (let ((new-section (vm-auto-report--section-direction)))
            (when new-section
              (setq section new-section)))
          (let ((conn (vm-auto-report--read-connection-line section submod-decls)))
            (when conn
              (push conn connections))))
        (forward-line 1)))
    (vm-auto-report--vector (nreverse connections))))

(defun vm-auto-report--auto-marker-kind (text)
  "Return a stable marker kind for TEXT."
  (cond ((string-match-p "AUTOINST" text) "AUTOINST")
        ((string-match-p "\\.\\*" text) "dot-star")
        (t text)))

(defun vm-auto-report--auto-instantiations (module-end)
  "Return AUTOINST/dot-star instantiations up to MODULE-END."
  (let (items)
    (save-excursion
      (while (verilog-re-search-forward-quick vm-auto-report--auto-re module-end t)
        (let ((marker-text (match-string-no-properties 0))
              (marker-beg (match-beginning 0))
              (marker-end (match-end 0)))
          (unless (verilog-inside-comment-or-string-p)
            (save-excursion
              (goto-char marker-beg)
              (let* ((submod (condition-case nil (verilog-read-inst-module) (error nil)))
                     (inst (condition-case nil (verilog-read-inst-name) (error nil)))
                     (submodi (and submod (vm-auto-report--lookup-module submod)))
                     (subdecls (and submodi
                                    (condition-case nil
                                        (verilog-modi-get-decls submodi)
                                      (error nil))))
                     (inst-open (condition-case nil
                                    (progn
                                      (verilog-backward-open-paren)
                                      (point))
                                  (error nil)))
                     (inst-end (and inst-open
                                    (condition-case nil
                                        (save-excursion
                                          (goto-char inst-open)
                                          (verilog-forward-sexp-ign-cmt 1)
                                          (point))
                                      (error nil)))))
                (when (and submod inst inst-end)
                  (push
                   `((module . ,submod)
                     (instance . ,inst)
                     (file . ,(vm-auto-report--module-file submodi))
                     (definition_type . ,(and submodi (verilog-modi-get-type submodi)))
                     (marker . ,(vm-auto-report--auto-marker-kind marker-text))
                     (location . ,(vm-auto-report--location marker-beg))
                     (connections . ,(vm-auto-report--generated-connections
                                      marker-end inst-end subdecls)))
                   items))))))))
    (vm-auto-report--vector (nreverse items))))

(defun vm-auto-report--read-identifier ()
  "Read a Verilog identifier at point and move past it, or return nil."
  (when (looking-at "\\([`a-zA-Z_$][a-zA-Z0-9_$]*\\|\\\\[^ \t\n\f]+\\s-\\)")
    (let ((identifier (match-string-no-properties 1)))
      (goto-char (match-end 0))
      identifier)))

(defun vm-auto-report--skip-line-space ()
  "Skip horizontal whitespace only."
  (skip-chars-forward " \t\f"))

(defun vm-auto-report--skip-head-p (name)
  "Return non-nil if NAME is not an instance cell type."
  (or (not name)
      (member name verilog-keywords)
      (member name verilog-gate-keywords)
      (member name
              '("assign" "always" "always_comb" "always_ff" "always_latch"
                "begin" "case" "casex" "casez" "class" "clocking"
                "covergroup" "else" "end" "endcase" "endclass"
                "endclocking" "endfunction" "endgenerate" "endgroup"
                "endinterface" "endmodule" "endpackage" "endprogram"
                "endproperty" "endtask" "final" "for" "forever" "fork"
                "function" "generate" "genvar" "if" "initial" "input"
                "inout" "interface" "join" "join_any" "join_none"
                "localparam" "logic" "module" "output" "package"
                "parameter" "program" "property" "reg" "task" "typedef"
                "wire"))))

(defun vm-auto-report--skip-parameter-list ()
  "Skip an optional #(...) parameter override at point."
  (verilog-forward-syntactic-ws)
  (when (looking-at "#")
    (forward-char 1)
    (verilog-forward-syntactic-ws)
    (when (looking-at "(")
      (condition-case nil
          (verilog-forward-sexp-ign-cmt 1)
        (error nil)))))

(defun vm-auto-report--skip-instance-array ()
  "Skip optional instance array dimensions."
  (verilog-forward-syntactic-ws)
  (while (looking-at "\\[")
    (condition-case nil
        (verilog-forward-sexp-ign-cmt 1)
      (error (forward-char 1)))
    (verilog-forward-syntactic-ws)))

(defun vm-auto-report--sexp-end-at-point ()
  "Return the balanced expression end at point, or nil."
  (condition-case nil
      (save-excursion
        (verilog-forward-sexp-ign-cmt 1)
        (point))
    (error nil)))

(defun vm-auto-report--instance-source (open close)
  "Return how an instance pin list between OPEN and CLOSE was generated."
  (let ((text (buffer-substring-no-properties open close)))
    (cond ((string-match-p "AUTOINST" text) "autoinst")
          ((string-match-p "\\.\\*" text) "dot-star")
          (t "manual"))))

(defun vm-auto-report--connection-end (limit)
  "Move to the next top-level comma or LIMIT."
  (let ((done nil))
    (while (and (not done) (< (point) limit))
      (cond ((looking-at "[ \t\n\f]+")
             (goto-char (match-end 0)))
            ((looking-at "/[/*]")
             (condition-case nil
                 (forward-comment 1)
               (error (forward-char 1))))
            ((looking-at "[({\\[]")
             (condition-case nil
                 (verilog-forward-sexp-ign-cmt 1)
               (error (forward-char 1))))
            ((looking-at ",")
             (setq done t))
            (t
             (forward-char 1)))))
  (point))

(defun vm-auto-report--read-named-connection (limit submod-decls)
  "Read a named port connection at point, or return nil."
  (when (looking-at "\\.\\s-*\\(\\*\\|[a-zA-Z_$][a-zA-Z0-9_$]*\\|\\\\[^ \t\n\f]+\\s-\\)")
    (let ((port (match-string-no-properties 1))
          expr)
      (goto-char (match-end 0))
      (verilog-forward-syntactic-ws)
      (cond ((equal port "*")
             `((style . "dot-star")
               (port . "*")
               (expr . "*")))
            ((looking-at "(")
             (let ((start (1+ (point)))
                   (end (vm-auto-report--sexp-end-at-point)))
               (when (and end (<= end limit))
                 (goto-char end)
                 (setq expr
                       (string-trim
                        (buffer-substring-no-properties start (1- end))))
                 (append `((style . "named"))
                         (vm-auto-report--connection nil port expr submod-decls)))))
            (t
             (setq expr port)
             (append `((style . "dot-name"))
                     (vm-auto-report--connection nil port expr submod-decls)))))))

(defun vm-auto-report--read-ordered-connection (index limit submod-decls port-order)
  "Read an ordered port connection at point."
  (let ((start (point))
        end expr port)
    (setq end (vm-auto-report--connection-end limit))
    (setq expr (string-trim (buffer-substring-no-properties start end)))
    (setq port (nth index port-order))
    (append `((style . "ordered")
              (index . ,index))
            (if port
                (vm-auto-report--connection nil port expr submod-decls)
              `((port . nil)
                (expr . ,expr))))))

(defun vm-auto-report--instance-connections (open close submod-decls port-order)
  "Return parsed connections in the instance port list from OPEN to CLOSE."
  (let ((limit (1- close))
        (index 0)
        connections)
    (save-excursion
      (goto-char (1+ open))
      (while (< (point) limit)
        (verilog-forward-syntactic-ws)
        (when (< (point) limit)
          (let ((conn (if (looking-at "\\.")
                          (vm-auto-report--read-named-connection limit submod-decls)
                        (vm-auto-report--read-ordered-connection
                         index limit submod-decls port-order))))
            (when conn
              (push conn connections))
            (setq index (1+ index))
            (verilog-forward-syntactic-ws)
            (when (looking-at ",")
              (forward-char 1))))))
    (vm-auto-report--vector (nreverse connections))))

(defun vm-auto-report--instance-terminator-ok-p (inst-end module-end)
  "Return non-nil if INST-END looks like an instance item terminator."
  (save-excursion
    (goto-char inst-end)
    (verilog-forward-syntactic-ws)
    (or (>= (point) module-end)
        (looking-at "[,;]"))))

(defun vm-auto-report--instance-item (module inst inst-start open close)
  "Return a JSON-ready normal instance entry."
  (let* ((submodi (vm-auto-report--lookup-module module))
         (subdecls (and submodi
                        (condition-case nil
                            (verilog-modi-get-decls submodi)
                          (error nil))))
         (port-order (vm-auto-report--port-order-from-modi submodi))
         (raw-connections (vm-auto-report--instance-connections
                           open close subdecls port-order))
         (connections (vm-auto-report--expand-dot-star-with-decls
                       raw-connections subdecls port-order)))
    (when (or submodi vm-auto-report-include-unresolved-instances)
      `((module . ,module)
        (instance . ,inst)
        (file . ,(vm-auto-report--module-file submodi))
        (definition_type . ,(and submodi (verilog-modi-get-type submodi)))
        (source . ,(vm-auto-report--instance-source open close))
        (location . ,(vm-auto-report--location inst-start))
        (connections . ,(vm-auto-report--vector connections))
        (unconnected_ports . ,(vm-auto-report--unconnected-ports
                               subdecls connections port-order))))))

(defun vm-auto-report--parse-instance-chain-at-line (module-end)
  "Parse a normal instance declaration beginning on the current line."
  (catch 'vm-auto-report--return
    (save-excursion
      (let (first cell items done)
        (beginning-of-line)
        (vm-auto-report--skip-line-space)
        (when (or (>= (point) module-end)
                  (looking-at "\\($\\|//\\|/\\*\\|`\\)"))
          (throw 'vm-auto-report--return nil))
        (setq first (vm-auto-report--read-identifier))
        (unless first
          (throw 'vm-auto-report--return nil))
        (vm-auto-report--skip-line-space)
        (setq cell
              (if (looking-at ":")
                  (progn
                    (forward-char 1)
                    (verilog-forward-syntactic-ws)
                    (vm-auto-report--read-identifier))
                first))
        (when (vm-auto-report--skip-head-p cell)
          (throw 'vm-auto-report--return nil))
        (vm-auto-report--skip-parameter-list)
        (while (not done)
          (verilog-forward-syntactic-ws)
          (let ((inst-start (point))
                (inst (vm-auto-report--read-identifier))
                open close item)
            (cond
             ((or (not inst)
                  (vm-auto-report--skip-head-p inst))
              (setq done t))
             (t
              (vm-auto-report--skip-instance-array)
              (setq open (point))
              (setq close (and (looking-at "(")
                               (vm-auto-report--sexp-end-at-point)))
              (cond
               ((not (and close
                          (<= close module-end)
                          (vm-auto-report--instance-terminator-ok-p
                           close module-end)))
                (setq done t))
               (t
                (setq item (vm-auto-report--instance-item
                            cell inst inst-start open close))
                (when item
                  (push item items))
                (goto-char close)
                (verilog-forward-syntactic-ws)
                (unless (looking-at ",")
                  (setq done t))
                (when (looking-at ",")
                  (forward-char 1))))))))
        (nreverse items)))))

(defun vm-auto-report--all-instantiations (module-end)
  "Return all normal instance declarations found up to MODULE-END."
  (let (items)
    (save-excursion
      (verilog-beg-of-defun-quick)
      (while (< (point) module-end)
        (unless (verilog-inside-comment-or-string-p)
          (setq items
                (append (nreverse
                         (vm-auto-report--parse-instance-chain-at-line module-end))
                        items)))
        (forward-line 1)))
    (vm-auto-report--vector (nreverse items))))

(defun vm-auto-report--modules ()
  "Return all design units in the current buffer."
  (let (modules)
    (save-excursion
      (goto-char (point-min))
      (while (re-search-forward vm-auto-report--defun-re nil t)
        (unless (verilog-inside-comment-or-string-p)
          (let ((type (match-string-no-properties 1)))
            (when (verilog-re-search-forward-quick "[(;]" nil t)
              (let* ((name (verilog-read-module-name))
                     (pt (point))
                     (end (save-excursion (verilog-get-end-of-defun)))
                     (modi (verilog-modi-new
                            name
                            (or (buffer-file-name) (current-buffer))
                            pt
                            type)))
                (save-excursion
                  (goto-char pt)
                  (push
                   `((name . ,name)
                     (type . ,type)
                     (location . ,(vm-auto-report--location pt))
                     (auto_signals . ,(vm-auto-report--auto-signals modi))
                     (submodules . ,(vm-auto-report--auto-instantiations end))
                     (instances . ,(vm-auto-report--all-instantiations end)))
                   modules))
                (goto-char end)))))))
    (vm-auto-report--vector (nreverse modules))))

(defun vm-auto-report--signal-name-from-expr (expr)
  "Return (name bits) from a simple signal expression EXPR."
  (when (and expr
             (string-match
              "\\`\\s-*\\([a-zA-Z_$][a-zA-Z0-9_$]*\\)\\s-*\\(\\[[^]]+\\]\\)?\\s-*\\'"
              expr))
    (list (match-string 1 expr)
          (match-string 2 expr))))

(defun vm-auto-report--interface-name-from-expr (expr)
  "Return the base interface instance name from EXPR."
  (when (and expr
             (string-match
              "\\`\\s-*\\([a-zA-Z_$][a-zA-Z0-9_$]*\\)\\(?:\\.[a-zA-Z_$][a-zA-Z0-9_$]*\\)?\\s-*\\'"
              expr))
    (match-string 1 expr)))

(defun vm-auto-report--numeric-range (bits)
  "Return (high low) when BITS is a numeric range or bit select."
  (cond ((and bits (string-match "\\`\\[\\([0-9]+\\):\\([0-9]+\\)\\]\\'" bits))
         (list (string-to-number (match-string 1 bits))
               (string-to-number (match-string 2 bits))))
        ((and bits (string-match "\\`\\[\\([0-9]+\\)\\]\\'" bits))
         (let ((bit (string-to-number (match-string 1 bits))))
           (list bit bit)))))

(defun vm-auto-report--merge-bits (old new)
  "Merge two bit ranges OLD and NEW, best effort."
  (cond ((not old) new)
        ((not new) old)
        ((equal old new) old)
        (t
         (let ((old-range (vm-auto-report--numeric-range old))
               (new-range (vm-auto-report--numeric-range new)))
           (if (and old-range new-range)
               (format "[%d:%d]"
                       (max (nth 0 old-range) (nth 0 new-range))
                       (min (nth 1 old-range) (nth 1 new-range)))
             old)))))

(defun vm-auto-report--add-unique (item items)
  "Add ITEM to ITEMS if not already present."
  (if (member item items) items (cons item items)))

(defun vm-auto-report--signal-source (inst conn)
  "Return a compact source string for INST/CONN."
  (let ((module (vm-auto-report--alist-get 'module inst))
        (instance (vm-auto-report--alist-get 'instance inst))
        (port (vm-auto-report--alist-get 'port conn))
        (index (vm-auto-report--alist-get 'index conn)))
    (if port
        (format "%s %s.%s" module instance port)
      (format "%s %s[%s]" module instance (or index "?")))))

(defun vm-auto-report--signal-endpoint (inst conn)
  "Return a structured endpoint record for INST/CONN."
  `((module . ,(vm-auto-report--alist-get 'module inst))
    (instance . ,(vm-auto-report--alist-get 'instance inst))
    (port . ,(vm-auto-report--alist-get 'port conn))
    (index . ,(vm-auto-report--alist-get 'index conn))
    (direction . ,(vm-auto-report--alist-get 'direction conn))
    (source . ,(vm-auto-report--signal-source inst conn))))

(defun vm-auto-report--endpoint-label (endpoint)
  "Return a compact label for ENDPOINT."
  (let ((instance (vm-auto-report--alist-get 'instance endpoint))
        (port (vm-auto-report--alist-get 'port endpoint))
        (index (vm-auto-report--alist-get 'index endpoint))
        (source (vm-auto-report--alist-get 'source endpoint)))
    (cond ((and instance port)
           (format "%s.%s" instance port))
          ((and instance index)
           (format "%s[%s]" instance index))
          ((stringp source)
           source)
          (t ""))))

(defun vm-auto-report--ordered-endpoints (endpoints)
  "Return ENDPOINTS in source appearance order."
  (nreverse (copy-sequence endpoints)))

(defun vm-auto-report--logic-comment-from-endpoints (endpoints)
  "Return relation text for logic ENDPOINTS."
  (when endpoints
    (let* ((ordered (vm-auto-report--ordered-endpoints endpoints))
           (drivers nil)
           (loads nil)
           (ambiguous nil))
      (dolist (endpoint ordered)
        (pcase (vm-auto-report--alist-get 'direction endpoint)
          ("output"
           (push endpoint drivers))
          ("input"
           (push endpoint loads))
          ("inout"
           (push endpoint ambiguous))
          (_
           (push endpoint ambiguous))))
      (let ((driver-labels (mapcar #'vm-auto-report--endpoint-label (nreverse drivers)))
            (load-labels (mapcar #'vm-auto-report--endpoint-label (nreverse loads)))
            (other-labels (mapcar #'vm-auto-report--endpoint-label (nreverse ambiguous))))
        (cond
         ((and (null load-labels) (null other-labels) (= (length driver-labels) 1))
          (format "from %s" (car driver-labels)))
         ((and (null driver-labels) (null other-labels) (= (length load-labels) 1))
          (format "to %s" (car load-labels)))
         ((and (= (length driver-labels) 1) load-labels (null other-labels))
          (format "from %s to %s"
                  (car driver-labels)
                  (mapconcat #'identity load-labels ", ")))
         ((and (= (length driver-labels) 1) (null load-labels) (= (length other-labels) 1))
         (format "connect %s and %s" (car driver-labels) (car other-labels)))
         ((> (length ordered) 1)
          (format "connect %s"
                  (mapconcat #'identity
                             (append driver-labels load-labels other-labels)
                             ", ")))
         ((= (length driver-labels) 1)
          (format "from %s" (car driver-labels)))
         ((= (length load-labels) 1)
          (format "to %s" (car load-labels)))
         (t
          (format "connect %s"
                  (mapconcat #'identity
                             (append driver-labels load-labels other-labels)
                             ", "))))))))

(defun vm-auto-report--interface-comment-from-endpoints (endpoints)
  "Return relation text for interface ENDPOINTS."
  (let* ((ordered (vm-auto-report--ordered-endpoints endpoints))
         (labels (mapcar #'vm-auto-report--endpoint-label ordered)))
    (cond
     ((null labels) nil)
     ((= (length labels) 1)
      (format "connect %s" (car labels)))
     ((= (length labels) 2)
      (format "connect %s with %s" (car labels) (cadr labels)))
     (t
      (format "connect %s with %s"
              (car labels)
              (mapconcat #'identity (cdr labels) ", "))))))

(defun vm-auto-report--relation-comment (kind endpoints)
  "Return a compact relation comment for KIND and ENDPOINTS."
  (cond ((equal kind "interface")
         (vm-auto-report--interface-comment-from-endpoints endpoints))
        ((equal kind "logic")
         (vm-auto-report--logic-comment-from-endpoints endpoints))
        (t nil)))

(defun vm-auto-report--expand-dot-star-connections (inst connections)
  "Expand .*-style CONNECTIONS for INST into per-port entries."
  (let* ((submodi (vm-auto-report--lookup-module
                   (vm-auto-report--alist-get 'module inst)))
         (subdecls (and submodi
                        (condition-case nil
                            (verilog-modi-get-decls submodi)
                          (error nil))))
         (port-order (vm-auto-report--port-order-from-modi submodi)))
    (vm-auto-report--expand-dot-star-with-decls
     connections subdecls port-order)))

(defun vm-auto-report--record-signal (name kind type bits signed inst conn records)
  "Add or update a signal declaration record."
  (let* ((source (vm-auto-report--signal-source inst conn))
         (endpoint (vm-auto-report--signal-endpoint inst conn))
         (record (assoc name records)))
    (if record
        (let ((entry (cdr record)))
          (setcdr (assq 'bits entry)
                  (vm-auto-report--merge-bits
                   (vm-auto-report--alist-get 'bits entry)
                   bits))
          (setcdr (assq 'signed entry)
                  (or (vm-auto-report--alist-get 'signed entry) signed))
          (setcdr (assq 'sources entry)
                  (vm-auto-report--add-unique
                   source
                   (vm-auto-report--alist-get 'sources entry)))
          (setcdr (assq 'endpoints entry)
                  (vm-auto-report--add-unique
                   endpoint
                   (vm-auto-report--alist-get 'endpoints entry)))
          (when (and type
                     (vm-auto-report--alist-get 'type entry)
                     (not (equal type (vm-auto-report--alist-get 'type entry))))
            (setcdr (assq 'notes entry)
                    (vm-auto-report--add-unique
                     (format "type conflict: %s vs %s"
                             (vm-auto-report--alist-get 'type entry)
                             type)
                     (vm-auto-report--alist-get 'notes entry))))
          records)
      (cons
       (cons name
             `((name . ,name)
               (kind . ,kind)
               (type . ,type)
               (bits . ,bits)
               (signed . ,signed)
               (sources . (,source))
               (endpoints . (,endpoint))
               (notes . nil)))
       records))))

(defun vm-auto-report--collect-module-signals (module)
  "Collect printable signal declarations for MODULE."
  (let (records skipped)
    (dolist (inst (vm-auto-report--items
                   (vm-auto-report--alist-get 'instances module)))
      (dolist (conn (vm-auto-report--expand-dot-star-connections
                     inst
                     (vm-auto-report--alist-get 'connections inst)))
        (let* ((direction (vm-auto-report--alist-get 'direction conn))
               (expr (vm-auto-report--alist-get 'expr conn))
               (port (vm-auto-report--alist-get 'port conn))
               (style (vm-auto-report--alist-get 'style conn))
               (source (vm-auto-report--signal-source inst conn))
               (bits (vm-auto-report--alist-get 'bits conn))
               (signed (vm-auto-report--alist-get 'signed conn))
               (type (vm-auto-report--alist-get 'type conn)))
          (cond
           ((and (equal style "dot-star") (equal port "*"))
            (push `((source . ,source)
                    (expr . ,expr)
                    (reason . "dot-star connection could not be expanded"))
                  skipped))
           ((or (not expr) (string-empty-p expr))
            nil)
           ((equal direction "interface")
            (let ((name (vm-auto-report--interface-name-from-expr expr)))
              (if (and name type)
                  (setq records
                        (vm-auto-report--record-signal
                         name "interface" type nil nil inst conn records))
                (push `((source . ,source)
                        (expr . ,expr)
                        (reason . "complex or unresolved interface expression"))
                      skipped))))
           ((member direction '("input" "output" "inout" "interfaced"))
            (let ((sig (vm-auto-report--signal-name-from-expr expr)))
              (if sig
                  (setq records
                        (vm-auto-report--record-signal
                         (nth 0 sig)
                         "logic"
                         "logic"
                         (or (nth 1 sig) bits)
                         signed
                         inst
                         conn
                         records))
                (push `((source . ,source)
                        (expr . ,expr)
                        (reason . "complex expression"))
                      skipped))))
           (t
            (push `((source . ,source)
                    (expr . ,expr)
                    (reason . "unresolved direction or port definition"))
                  skipped))))))
    (list (nreverse records) (nreverse skipped))))

(defun vm-auto-report--decl-type-string (record)
  "Return declaration type text for RECORD."
  (let* ((entry (cdr record))
         (kind (vm-auto-report--alist-get 'kind entry))
         (type (vm-auto-report--alist-get 'type entry))
         (bits (vm-auto-report--alist-get 'bits entry))
         (signed (vm-auto-report--alist-get 'signed entry)))
    (cond ((equal kind "interface")
           (or type "interface"))
          (t
           (string-join
            (delq nil
                  (list "logic"
                        (and signed "signed")
                        bits))
            " ")))))

(defun vm-auto-report--format-comment (record)
  "Return source comment text for RECORD."
  (let* ((entry (cdr record))
         (kind (vm-auto-report--alist-get 'kind entry))
         (endpoints (vm-auto-report--alist-get 'endpoints entry))
         (sources (sort (copy-sequence
                         (vm-auto-report--alist-get 'sources entry))
                        #'string<))
         (notes (sort (copy-sequence
                       (vm-auto-report--alist-get 'notes entry))
                      #'string<))
         (relation (and endpoints
                        (vm-auto-report--relation-comment kind endpoints)))
         (text (if (and relation (not (string-empty-p relation)))
                   relation
                 (mapconcat #'identity sources ", "))))
    (when notes
      (setq text (concat text "; " (mapconcat #'identity notes ", "))))
    text))

(defun vm-auto-report--pad-right (text width)
  "Return TEXT padded with spaces to WIDTH."
  (concat text (make-string (max 0 (- width (length text))) ?\s)))

(defun vm-auto-report--insert-records (records kind)
  "Insert declaration RECORDS matching KIND."
  (let* ((filtered (sort
                    (seq-filter
                     (lambda (record)
                       (equal kind
                              (vm-auto-report--alist-get 'kind (cdr record))))
                     records)
                    (lambda (a b) (string< (car a) (car b)))))
         (type-width 1))
    (dolist (record filtered)
      (setq type-width
            (max type-width (length (vm-auto-report--decl-type-string record)))))
    (if filtered
        (dolist (record filtered)
          (let* ((entry (cdr record))
                 (type-text (vm-auto-report--decl-type-string record))
                 (type-padded (vm-auto-report--pad-right type-text type-width))
                 (name (vm-auto-report--alist-get 'name entry))
                 (comment (vm-auto-report--format-comment record))
                 (decl (if (equal kind "interface")
                           (format "%s %s ();" type-padded name)
                         (format "%s %s;" type-padded name))))
            (insert (format "%-48s // %s\n" decl comment))))
      (insert "// none\n"))))

(defun vm-auto-report--insert-skipped (skipped)
  "Insert skipped declaration expressions."
  (if skipped
      (dolist (item skipped)
        (insert
         (format "// %-32s expr=%S reason=%s\n"
                 (or (vm-auto-report--alist-get 'source item) "")
                 (or (vm-auto-report--alist-get 'expr item) "")
                 (or (vm-auto-report--alist-get 'reason item) ""))))
    (insert "// none\n")))

(defun vm-auto-report-signal-text (report)
  "Return the signal.txt contents for REPORT."
  (with-temp-buffer
    (insert "// Generated by ex.el\n")
    (insert (format "// Source: %s\n\n"
                    (or (vm-auto-report--alist-get 'source_file report) "")))
    (dolist (module (vm-auto-report--items
                     (vm-auto-report--alist-get 'modules report)))
      (let* ((name (vm-auto-report--alist-get 'name module))
             (type (vm-auto-report--alist-get 'type module))
             (collected (vm-auto-report--collect-module-signals module))
             (records (nth 0 collected))
             (skipped (nth 1 collected)))
        (insert "///////////////////////////////////////////////////////////////////////////////\n")
        (insert (format "// %s: %s\n" (capitalize (or type "module")) name))
        (insert "///////////////////////////////////////////////////////////////////////////////\n\n")
        (insert "// Logic interconnect declarations\n")
        (vm-auto-report--insert-records records "logic")
        (insert "\n// Interface interconnect declarations\n")
        (vm-auto-report--insert-records records "interface")
        (insert "\n// Connections that were not converted to declarations\n")
        (vm-auto-report--insert-skipped skipped)
        (insert "\n")))
    (buffer-string)))

(defun vm-auto-report--format-port-type (port)
  "Return compact type text for an unconnected PORT."
  (string-join
   (delq nil
         (list (vm-auto-report--alist-get 'type port)
               (and (vm-auto-report--alist-get 'signed port) "signed")
               (vm-auto-report--alist-get 'bits port)
               (vm-auto-report--alist-get 'multidim port)
               (vm-auto-report--alist-get 'memory port)
               (let ((modport (vm-auto-report--alist-get 'modport port)))
                 (and modport (concat "." modport)))))
   " "))

(defun vm-auto-report-unconnect-text (report)
  "Return the unconnect.txt contents for REPORT."
  (with-temp-buffer
    (let ((found nil))
      (insert "// Generated by ex.el\n")
      (insert (format "// Source: %s\n\n"
                      (or (vm-auto-report--alist-get 'source_file report) "")))
      (dolist (module (vm-auto-report--items
                       (vm-auto-report--alist-get 'modules report)))
        (let ((module-name (vm-auto-report--alist-get 'name module))
              (module-had nil))
          (dolist (inst (vm-auto-report--items
                         (vm-auto-report--alist-get 'instances module)))
            (let ((ports (vm-auto-report--items
                          (vm-auto-report--alist-get 'unconnected_ports inst))))
              (when ports
                (setq found t
                      module-had t)
                (insert (format "Module   : %s\n" module-name))
                (insert (format "Instance : %s %s\n"
                                (or (vm-auto-report--alist-get 'module inst) "")
                                (or (vm-auto-report--alist-get 'instance inst) "")))
                (insert (format "File     : %s\n"
                                (or (vm-auto-report--alist-get 'file inst) "UNRESOLVED")))
                (insert (format "Source   : %s\n"
                                (or (vm-auto-report--alist-get 'source inst) "")))
                (insert "Unconnected ports:\n")
                (dolist (port ports)
                  (insert
                   (format "  %-10s %-24s %-8s %s\n"
                           (or (vm-auto-report--alist-get 'direction port) "")
                           (or (vm-auto-report--alist-get 'port port) "")
                           (or (vm-auto-report--alist-get 'reason port) "")
                           (vm-auto-report--format-port-type port))))
                (insert "\n"))))
          (when module-had
            (insert "\n"))))
      (unless found
        (insert "No unconnected ports found.\n")))
    (buffer-string)))

(defun vm-auto-report-output-directory (output)
  "Return the output directory for sidecar text files."
  (if (and output (not (equal output "-")))
      (file-name-directory (expand-file-name output))
    default-directory))

(defun vm-auto-report-write-text-files (report output)
  "Write signal.txt and unconnect.txt for REPORT next to OUTPUT."
  (let ((dir (vm-auto-report-output-directory output)))
    (with-temp-file (expand-file-name "signal.txt" dir)
      (insert (vm-auto-report-signal-text report)))
    (with-temp-file (expand-file-name "unconnect.txt" dir)
      (insert (vm-auto-report-unconnect-text report)))))

(defun vm-auto-report--append-extra-flags (flags)
  "Append extra verilog library FLAGS to the current buffer."
  (when flags
    (make-local-variable 'verilog-library-flags)
    (setq verilog-library-flags
          (append verilog-library-flags flags))))

(defun vm-auto-report-file (file &optional library-flags)
  "Return a JSON-ready AUTO report for FILE.
LIBRARY-FLAGS, when non-nil, is appended to `verilog-library-flags'."
  (let* ((abs-file (expand-file-name file))
         (buf (find-file-noselect abs-file))
         (extra-flags (and library-flags (copy-sequence library-flags))))
    (with-current-buffer buf
      (unless (eq major-mode 'verilog-mode)
        (verilog-mode))
      (vm-auto-report--append-extra-flags extra-flags)
      (let ((verilog-before-getopt-flags-hook
             (cons (lambda ()
                     (vm-auto-report--append-extra-flags extra-flags))
                   verilog-before-getopt-flags-hook)))
        (if vm-auto-report-run-auto
            (verilog-auto)
          (verilog-auto-reeval-locals)
          (verilog-getopt-flags)))
      `((source_file . ,abs-file)
        (ran_verilog_auto . ,(and vm-auto-report-run-auto t))
        (library_flags . ,(vm-auto-report--vector verilog-library-flags))
        (modules . ,(vm-auto-report--modules))))))

(defun vm-dump-auto (file &optional output library-flags)
  "Dump FILE's AUTO connectivity report to OUTPUT.
When OUTPUT is nil or \"-\", print JSON to stdout.  LIBRARY-FLAGS is an
optional list appended to `verilog-library-flags'."
  (let* ((report (vm-auto-report-file file library-flags))
         (json-text (concat (vm-auto-report--json report) "\n")))
    (cond ((and output (not (equal output "-")))
           (with-temp-file output
             (insert json-text)))
          (t
           (princ json-text)))
    (when vm-auto-report-write-text-files
      (vm-auto-report-write-text-files report output))
    json-text))

(defun vm-dump-auto-cli ()
  "CLI entry for `vm-dump-auto'.
Usage:
  emacs -Q --batch -l ./ex.el -f vm-dump-auto-cli -- top.sv report.json

Remaining arguments after OUTPUT are appended to `verilog-library-flags',
for example:
  -- top.sv report.json -y rtl +libext+.v+.sv"
  (let ((args (copy-sequence command-line-args-left)))
    (when (equal (car args) "--")
      (setq args (cdr args)))
    (unless args
      (error "Usage: vm-dump-auto-cli -- INPUT [OUTPUT|-] [verilog-library-flags...]"))
    (let ((input (pop args))
          (output (pop args)))
      (vm-dump-auto input output args))))

(provide 'ex)

;;; ex.el ends here
