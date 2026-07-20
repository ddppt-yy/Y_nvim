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
(require 'subr-x)

(defvar vm-auto-report-run-auto t
  "Non-nil means `vm-dump-auto' runs `verilog-auto' before reporting.")

(defvar vm-auto-report-pretty-json t
  "Non-nil means `vm-dump-auto' writes formatted JSON.")

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
                     (submodules . ,(vm-auto-report--auto-instantiations end)))
                   modules))
                (goto-char end)))))))
    (vm-auto-report--vector (nreverse modules))))

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
  (let ((json-text (concat (vm-auto-report--json
                            (vm-auto-report-file file library-flags))
                           "\n")))
    (cond ((and output (not (equal output "-")))
           (with-temp-file output
             (insert json-text)))
          (t
           (princ json-text)))
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
