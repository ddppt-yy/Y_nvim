import re
import pathlib


def get_vhdl_port(fname: str):
    vhdl = {
        'name': "",
        'para': [],
        'port': []}
    found = False
    ptn_component = r'^\s*entity\s+(\w+)\s+is(.*)end\s+entity'
    re_component = re.compile(ptn_component, re.I | re.M | re.S)

    ptn_gene = r'^\s*generic\s*\((.*?)\)\s*;.*?'
    re_gene = re.compile(ptn_gene, re.I | re.M | re.S)

    ptn_port = r'^\s*port\s*\((.*)\)\s*;'
    re_port = re.compile(ptn_port, re.I | re.M | re.S)

    ptn_para = r'^\s*(\w+)\s*:\s*.*=?\s*(\w+);?.*$'
    re_para = re.compile(ptn_para)

    ptn_signal = r'^\s*(\w+)\s*:\s*(in|out)\s+(\w+).*$'
    re_signal = re.compile(ptn_signal)

    vfile = pathlib.Path(fname)
    text = vfile.read_text(encoding='utf-8')
    for m0 in re.finditer(re_component, text):
        if not m0:
            continue

        found = True
        vhdl['name'] = m0.group(1)
        # port
        m1 = re.search(re_port, m0.group(2))
        if m1:
            port_content = m1.group(1)
            for item in port_content.split('\n'):
                line = item.strip()
                if not line or line.startswith('--'):
                    continue
                m3 = re.search(re_signal, line)
                if m3:
                    signal = m3.group(1)
                    in_out = m3.group(2)
                    sig_type = m3.group(3)
                    vhdl['port'].append((signal, in_out, sig_type))
                else:
                    print('[E] signal not found: %s')
        else:
            print('[E] port not found!')
        # para
        mp = re.search(re_gene, m0.group(2))
        if mp:
            gene_content = mp.group(1)
            for item in gene_content.split('\n'):
                line = item.strip()
                if not line or line.startswith('--'):
                    continue
                m4 = re.search(re_para, line)
                if m4:
                    pname = m4.group(1)
                    pnum = m4.group(2)
                    vhdl['para'].append((pname, pnum))
                else:
                    print('[E] signal not found: %s')
    if not found:
        print('[E] port not found: %s' + fname)
    return vhdl


if __name__ == '__main__':
    p = './test/test.vhd'
    v = get_vhdl_port(p)
    print(v)
