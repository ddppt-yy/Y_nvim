













import sys
import re
import os
from sv_parser import SvParser
from typing import List, Tuple


def replace_brackets_with_spaces(data):
    if isinstance(data, list):
        return [replace_brackets_with_spaces(item) for item in data]
    elif isinstance(data, str):
        return data.replace('[', '    ').replace(']', '    ')
    else:
        return data


def align_strings(str_list: List[str]) -> List[str]:
    parsed_list = []
    for s in str_list:
        parts = re.findall(r'\[(.*?)\]', s)
        parsed = []
        for part in parts:
            if ':' in part:
                left, right = part.split(':', 1)
                parsed.append((left, right, True))
            else:
                parsed.append((part, '', False))
        parsed_list.append(parsed)

    max_columns = max(len(parsed) for parsed in parsed_list) if parsed_list else 0

    left_widths = [0] * max_columns
    right_widths = [0] * max_columns
    has_colon_list = [False] * max_columns
    for parsed in parsed_list:
            for col, (left, right, has_colon) in enumerate(parsed):
                if col >= max_columns:
                    continue
                left_widths[col] = max(left_widths[col], len(left))
                if has_colon:
                    right_widths[col] = max(right_widths[col], len(right))
                    has_colon_list[col] = True

    aligned_list = []
    for parsed in parsed_list:
        aligned_parts = []
        for col in range(max_columns):
            if col < len(parsed):
                left, right, has_colon = parsed[col]
                if has_colon_list[col]:
                    left_str = left.ljust(left_widths[col])
                    right_str = right.rjust(right_widths[col])
                    separator = ':' if has_colon else ' '
                    content = left_str + separator + right_str
                    aligned_parts.append(f'!{content}@' if not content.isspace() else ' '*(len(content)+2))
                else:
                    content = left.ljust(left_widths[col])
                    # aligned_parts.append(f'!{content}@')
                    aligned_parts.append(f'!{content}@' if not content.isspace() else ' '*(len(content)+2))
            else:
                aligned_parts.append('')
        aligned_list.append(''.join(aligned_parts))


    max_length = max(len(s) for s in aligned_list)
    equalized_list = [s + ' ' * (max_length - len(s)) for s in aligned_list]

    return   equalized_list

def parse_and_align_sv_code(code):
    codes = code.split('\n')

    codes_rm_comment = []
    for i in codes:
        tmp = re.sub(r'\s*//.*$', "", i, flags=re.M)
        tmp = re.sub(r'\s*$', "", tmp, flags=re.M)
        if tmp != "":
            codes_rm_comment.append(tmp)

    end = ',' if codes_rm_comment[-1][-1] == ',' else ''
    if codes_rm_comment[-1].endswith(','):
        typ = "port"
    elif codes_rm_comment[-1].endswith(';'):
        if 'parameter' in codes_rm_comment[-1]:
            typ = "para"
        elif 'localparam' in codes_rm_comment[-1]:
            typ = "para"
        else:
            typ = "signal"
    else:
        typ = "port"


    if typ == "port":
        if codes_rm_comment[-1].endswith(','):
            codes_rm_comment[-1] = re.sub(r'\s*,$', "", codes_rm_comment[-1], flags=re.M)

    with open("output_format_v.sv", "w", encoding="utf-8") as file:
        if typ == "port":
            file.writelines("module output_format_v (\n")
            for i in codes_rm_comment:
                file.writelines(i+'\n')
            file.writelines(");\n")
            file.writelines("endmodule\n")
        else:
            file.writelines("module output_format_v (); \n")
            for i in codes_rm_comment:
                file.writelines(i+'\n')
            file.writelines("endmodule\n")
    sv = SvParser("output_format_v.sv")
    sv_parser = sv.get_sv_port()
    os.remove("output_format_v.sv")

    pack_list = []
    unpack_list = []
    port_list = []
    if typ == "port":
        for i in sv_parser['port']:
            if len(i)==5:
                pack_list.append(i[3])
                unpack_list.append(i[4])
                port_list.append('['+i[1]+']' +
                    str('['+i[2]+']' if i[2] != "" else "[]") +
                    '[_pack___]'+
                    '['+i[0]+']'+
                    '[_unpack___]'
                    )
            elif len(i) == 2:
                pack_list.append(  '[ ]')
                unpack_list.append('[ ]')
                port_list.append('['+i[1][0]+"."+i[1][1]+']'+'[]'+"[_pack___]"+'['+i[0]+']'+"[_unpack___]" )
    elif typ == "signal":
        for i in sv_parser['signal']:
            pack_list.append(i[2])
            unpack_list.append(i[3])
            port_list.append(
                str('['+i[1]+']' if i[1] != "" else "[]") +
                '[_pack___]'+
                '['+i[0]+']'+
                '[_unpack___]'
                )

    pack_list_format   = align_strings(pack_list)
    unpack_list_format = align_strings(unpack_list)
    port_list_format   = align_strings(port_list)

    port_list_new = []
    for i in range(len(port_list_format)):
        tmp = re.sub(r'!', " ", port_list_format[i], flags=re.M)
        tmp = re.sub(r'@', " ", tmp, flags=re.M)
        tmp = re.sub(r' _pack___', pack_list_format[i], tmp, flags=re.M)
        tmp = re.sub(r' _unpack___', unpack_list_format[i], tmp, flags=re.M)
        tmp = re.sub(r'!', "[", tmp, flags=re.M)
        tmp = re.sub(r'@', "]", tmp, flags=re.M)
        port_list_new.append(tmp)
    out = []
    out_num = 0
    max_num = len(port_list_new)-1

    for num in range(len(codes)):
        if typ == 'port':
            if out_num==max_num:
                end_str = end
            else:
                end_str = ','
        else:
            end_str = ';'

        if bool(re.match(r'^\s*//', codes[num])):
            out.append(codes[num])
        elif bool(re.match(r'^\s*`', codes[num])):
            out.append(codes[num])
        # elif codes[num].isspace() or codes[num]=="":
        #     out.append(' '*3+codes[num])
        elif bool(re.match(r'^\s*$', codes[num])):
            out.append(codes[num])
        elif '//' in codes[num]:
            tmp = '//' + codes[num].split('//',1)[1]
            out.append(' '*3+port_list_new[out_num] + end_str + tmp)
            out_num=out_num+1
        else:
            out.append(' '*3+port_list_new[out_num] + end_str)
            out_num=out_num+1
    return '\n'.join(out)



if __name__ == "__main__":
    debug = 1
    if debug :
        input_code = """
                //aosl;fjkldsaflk,

            //aa
            input  logic clk,
            input  logic resten,
            input  reg [AA   -   1*6:0] a[NN],
            input      [AA   -   1:0+2] ar[NN],
            input  wire [BB    -  1   :   0] aa[NN],

            intf.master iii [NN-1:0],
            intf.slave  ooo [NN-1:0],

            input op [AA-1:0] [BB-1  :  0] fuck [NN-1:0   ] [CC] , //asda
            input op [AA-1:0] fuck1 [NN-1:0] [CC] , //asda
            input op [AA- 1:0] fuck2 [CC] , //asda
            input op [AA-1:0] fuck3 , //asda

            output  logic [CC-1:0] out[NN]        //asdf
        """

        input_code = """
            //sdf;lsj
            logic [ EE1-1:0 ]         tmp_logic [ NN-1+3:0 ] ;   //sajio;fdjoasj
            wire  [ EE2-1:0 ]          tmp1_wire [ NN-1:0 ] ;
            reg   [ EE3-1:0 ] [ AA:5] tmp2_reg  [ NN-1:0 ] [NN] ;
            //daf;sjklf

            logic   a_l;
            wire    a_w;
            reg     a_r;


            userdef xxx[3];

            a_intf_if a_intf();
            b_intf_if b_intf();

        """
    else:
        input_code = sys.stdin.read()
    formatted_code = parse_and_align_sv_code(input_code)
    sys.stdout.write(formatted_code)

