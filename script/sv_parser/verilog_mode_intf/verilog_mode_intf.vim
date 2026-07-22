" -------------------------------------------------------
" Created by     : https://github.com/ddppt-yy
" Filename       : verilog_mode_py.vim
" Author         : ddppt-yy
" Created On     : 2026/07/22 09:12
" Last Modified  : 2026/07/22 09:12
" Version        : v1.0
" Description    : 
" -------------------------------------------------------

if exists("loaded_verilog_emacsauto")
   finish
endif
let loaded_verilog_emacsauto = 1

noremap <unique> <script> <Plug>VerilogEmacsAutoAdd    <SID>Add
noremap <unique> <script> <Plug>VerilogEmacsAutoDelete <SID>Delete
noremap <unique> <script> <Plug>VerilogEmacsAutoExternal <SID>External
noremap <unique> <script> <Plug>VerilogEmacsAutoInternal <SID>Internal
noremap <unique> <script> <Plug>VerilogEmacsAutoReport   <SID>Rpt
noremap <SID>Add    :call <SID>Add()<CR>
noremap <SID>Delete :call <SID>Delete()<CR>
noremap <SID>External :call <SID>External()<CR>
noremap <SID>Internal :call <SID>Internal()<CR>
noremap <SID>Rpt      :call <SID>Rpt()<CR>
" add menu items for gvim
noremenu <script> Plugin.Verilog\ AddAuto    <SID>Add
noremenu <script> Plugin.Verilog\ DeleteAuto <SID>Delete
noremenu <script> Plugin.Verilog\ AddExternalSignal <SID>External
noremenu <script> Plugin.Verilog\ AddInternalSignal <SID>Internal
noremenu <script> Plugin.Verilog\ GenUnconnectReport <SID>Rpt

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

function s:InsertSignalReport(mode)
   let l:cmd = 'emacs -Q --batch -l ~/.vim/plugin/ex.el'
         \ . ' -f vm-dump-auto-cli -- '
         \ . shellescape(expand('%:p')) . ' ' . a:mode
   call append(line('.') - 1, systemlist(l:cmd))
endfunction

function s:External()
   call s:InsertSignalReport('-ex')
endfunction

function s:Internal()
   call s:InsertSignalReport('-in')
endfunction

function s:Rpt()
   let l:json = expand('%:p') . '.auto_report.json'
   execute '!emacs -Q --batch -l ~/.vim/plugin/ex.el'
         \ . ' -f vm-dump-auto-cli -- '
         \ . shellescape(expand('%:p')) . ' ' . shellescape(l:json)
endfunction

function! VerilogAddAuto()
    call s:Add()
endfunction

command! VerilogAdd call VerilogAddAuto()
command! VerilogAddExternalSignal call s:External()
command! VerilogAddInternalSignal call s:Internal()
command! VerilogGenUnconnectReport call s:Rpt()
