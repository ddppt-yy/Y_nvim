import sys
import os
import pathlib
from vhdl_parser import get_vhdl_port
from sv_parser import SvParser

if len(sys.argv) < 2:
    print("input error")
    sys.exit(1)

filename = sys.argv[1]
vfile = pathlib.Path(filename)

file_extension = os.path.splitext(vfile)[1]
if 'vh' in file_extension:
    vdict = get_vhdl_port(vfile)
else:
    sv = SvParser(vfile)
    vdict = sv.get_sv_port()

para_max = 0
for p in vdict['para']:
    l = len(p[0])
    if l > para_max:
        para_max = l

para_item_max = 0
for p in vdict['para']:
    l = len(p[1])
    if l > para_item_max:
        para_item_max = l

port_max = 0
for p in vdict['port']:
    l = len(p[0])
    if l > port_max:
        port_max = l


if vdict['para'] == []:
    print("{0} i_{0}_0 (".format(vdict['name']))
else:
    print("{0} #(".format(vdict['name']))
    for p in vdict['para']:
        if p == vdict['para'][-1]:
            end = ""
        else:
            end = ","
        print("    .{0}{1}( {2}{3}){4}".format(p[0], ' '*(para_max+4 -
              len(p[0])), p[1], ' '*(para_item_max+1-len(p[1])), end))
    print(") i_{0}_0 (".format(vdict['name']))

for p in vdict['port']:
    if p == vdict['port'][-1]:
        end = " "
    else:
        end = ","
    if "in" in p[1]:
        io = "//i"
    elif "out" in p[1]:
        io = "//o"
    else:
        io = "//intf "+p[1][1]
    print("    .{0}{3}( {0}{3}){1}{2}".format(p[0], end, io, ' '*(port_max+1-len(p[0]))))

print(");")
