" -------------------------------------------------------
" Created by     : https://github.com/ddppt-yy
" Filename       : verilog_mode_py.vim
" Author         : ddppt-yy
" Created On     : 2026/07/22 09:12
" Last Modified  : 2026/07/22 09:12
" Version        : v1.0
" Description    : 
" //external_intf_begin
" //external_intf_end
" //inner_intf_begin
" //inner_intf_end
" -------------------------------------------------------

if exists("loaded_verilog_mode_intf")
   finish
endif
let loaded_verilog_mode_intf = 1
let s:script_dir = expand('<sfile>:p:h')

noremap <unique> <script> <Plug>VerilogEmacsAutoAdd    <SID>Add
noremap <unique> <script> <Plug>VerilogEmacsAutoDelete <SID>Delete
noremap <unique> <script> <Plug>VerilogEmacsAutoExternal <SID>External
noremap <unique> <script> <Plug>VerilogEmacsAutoInternal <SID>Internal
noremap <unique> <script> <Plug>VerilogEmacsAutoInsertIntf <SID>AutoInsertIntf
noremap <unique> <script> <Plug>VerilogEmacsAutoInsertDelate <SID>AutoInsertDelate
noremap <unique> <script> <Plug>VerilogEmacsAutoReport   <SID>Rpt
noremap <SID>Add    :call <SID>Add()<CR>
noremap <SID>Delete :call <SID>Delete()<CR>
noremap <SID>External :call <SID>External()<CR>
noremap <SID>Internal :call <SID>Internal()<CR>
noremap <SID>AutoInsertIntf :call <SID>AutoInsertIntf()<CR>
noremap <SID>AutoInsertDelate :call <SID>AutoInsertDelate()<CR>
noremap <SID>Rpt      :call <SID>Rpt()<CR>
" add menu items for gvim
noremenu <script> SvConnect.Verilog\ AddAuto    <SID>Add
noremenu <script> SvConnect.Verilog\ DeleteAuto <SID>Delete
noremenu <script> SvConnect.Verilog\ AddExternalSignal <SID>External
noremenu <script> SvConnect.Verilog\ AddInternalSignal <SID>Internal
noremenu <script> SvConnect.Verilog\ AutoInsertIntf <SID>AutoInsertIntf
noremenu <script> SvConnect.Verilog\ AutoInsertDelate <SID>AutoInsertDelate
noremenu <script> SvConnect.Verilog\ GenUnconnectReport <SID>Rpt

function s:Add()
   if &expandtab
      let s:save_tabstop = &tabstop
      let &tabstop=8
   endif
   w! %.emacsautotmp
   !emacs -batch -l ~/.vim/plugin/verilog-mode.el %.emacsautotmp -f verilog-batch-auto
   %!cat %.emacsautotmp 
   if &expandtab
      retab
      let &tabstop=s:save_tabstop
   endif
   !rm %.emacsautotmp -f
endfunction

function s:Delete()
   w! %.emacsautotmp
   !emacs -batch -l ~/.vim/plugin/verilog-mode.el %.emacsautotmp -f verilog-batch-delete-auto
   %!cat %.emacsautotmp 
   !rm %.emacsautotmp -f
endfunction

function s:PluginFile(filename)
   let l:local = s:script_dir . '/' . a:filename
   if filereadable(l:local)
      return l:local
   endif
   return expand('~/.vim/plugin/' . a:filename)
endfunction

function s:InsertSignalReport(mode)
   call append(line('.') - 1, s:GetSignalReport(a:mode))
endfunction

function s:GetSignalReport(mode)
   let l:cmd = 'emacs -Q --batch -l ' . shellescape(s:PluginFile('ex.el'))
         \ . ' -f vm-dump-auto-cli -- '
         \ . shellescape(expand('%:p')) . ' ' . a:mode
   return systemlist(l:cmd)
endfunction

function s:FormatExternalPortLine(line, delimiter)
   let l:line = substitute(a:line, '\s*();\(\s*//\)', a:delimiter . '\1', '')
   let l:line = substitute(l:line, ';\(\s*//\)', a:delimiter . '\1', '')
   let l:line = substitute(l:line, '\s*();\s*$', a:delimiter, '')
   let l:line = substitute(l:line, ';\s*$', a:delimiter, '')
   return l:line
endfunction

function s:FormatExternalPortList(lines)
   let l:lines = copy(a:lines)
   let l:decl_lnums = []

   for l:idx in range(0, len(l:lines) - 1)
      if l:lines[l:idx] =~# '^\s*\S'
            \ && l:lines[l:idx] !~# '^\s*//'
            \ && l:lines[l:idx] =~# ';\(\s*//\|\s*$\)'
         call add(l:decl_lnums, l:idx)
      endif
   endfor

   for l:idx in l:decl_lnums
      let l:delimiter = l:idx == l:decl_lnums[-1] ? '' : ','
      let l:lines[l:idx] = s:FormatExternalPortLine(l:lines[l:idx], l:delimiter)
   endfor

   return l:lines
endfunction

function s:GetAutoInsertReport(mode)
   let l:lines = s:GetSignalReport(a:mode)
   if a:mode ==# '-ex'
      return s:FormatExternalPortList(l:lines)
   endif
   return l:lines
endfunction

function s:External()
   call s:InsertSignalReport('-ex')
endfunction

function s:Internal()
   call s:InsertSignalReport('-in')
endfunction

function s:Rpt()
   let l:json = expand('%:p') . '.auto_report.json'
   execute '!emacs -Q --batch -l ' . shellescape(s:PluginFile('ex.el'))
         \ . ' -f vm-dump-auto-cli -- '
         \ . shellescape(expand('%:p')) . ' ' . shellescape(l:json)
endfunction

function s:FindMarkerRange(begin_pat, end_pat)
   let l:begin_lnum = 0
   let l:end_lnum = 0
   for l:lnum in range(1, line('$'))
      if getline(l:lnum) =~# a:begin_pat
         let l:begin_lnum = l:lnum
         break
      endif
   endfor

   if l:begin_lnum == 0
      return [0, 0]
   endif

   for l:lnum in range(l:begin_lnum + 1, line('$'))
      if getline(l:lnum) =~# a:end_pat
         let l:end_lnum = l:lnum
         break
      endif
   endfor

   return [l:begin_lnum, l:end_lnum]
endfunction

function s:DeleteMarkerRange(begin_pat, end_pat)
   let [l:begin_lnum, l:end_lnum] = s:FindMarkerRange(a:begin_pat, a:end_pat)
   if l:begin_lnum == 0 || l:end_lnum == 0
      return 0
   endif
   if l:end_lnum > l:begin_lnum + 1
      execute (l:begin_lnum + 1) . ',' . (l:end_lnum - 1) . 'delete _'
   endif
   return 1
endfunction

function s:ReplaceMarkerRange(begin_pat, end_pat, mode)
   let l:ok = s:DeleteMarkerRange(a:begin_pat, a:end_pat)
   if !l:ok
      return 0
   endif

   let [l:begin_lnum, l:end_lnum] = s:FindMarkerRange(a:begin_pat, a:end_pat)
   call append(l:begin_lnum, s:GetAutoInsertReport(a:mode))
   return 1
endfunction

function s:IntfMarkerRanges()
   return [
         \ ['^\s*//\s*external_intf_begin\s*$', '^\s*//\s*external_intf_end\s*$', '-ex'],
         \ ['^\s*//\s*inn\(er\|el\)_intf_begin\s*$', '^\s*//\s*inn\(er\|el\)_intf_end\s*$', '-in'],
         \ ]
endfunction

function s:AutoInsertIntf()
   let l:inserted = 0
   for l:item in s:IntfMarkerRanges()
      let l:inserted += s:ReplaceMarkerRange(l:item[0], l:item[1], l:item[2])
   endfor
   if l:inserted == 0
      echohl WarningMsg
      echom 'AutoInsertIntf: no external/inner interface marker ranges found'
      echohl None
   endif
endfunction

function s:AutoInsertDelate()
   let l:deleted = 0
   for l:item in s:IntfMarkerRanges()
      let l:deleted += s:DeleteMarkerRange(l:item[0], l:item[1])
   endfor
   if l:deleted == 0
      echohl WarningMsg
      echom 'AutoInsertDelate: no external/inner interface marker ranges found'
      echohl None
   endif
endfunction

function! VerilogAddAuto()
    call s:Add()
endfunction

function! AutoInsertIntf()
    call s:AutoInsertIntf()
endfunction

function! AutoInsertDelate()
    call s:AutoInsertDelate()
endfunction

command! VerilogAdd call VerilogAddAuto()
command! VerilogAddExternalSignal call s:External()
command! VerilogAddInternalSignal call s:Internal()
command! VerilogGenUnconnectReport call s:Rpt()
command! AutoInsertIntf call AutoInsertIntf()
command! AutoInsertDelate call AutoInsertDelate()
