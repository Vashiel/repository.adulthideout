# -*- coding: utf-8 -*-

def calcseed(lc, hr):
    f = lc.replace('$', '').replace('0', '1')
    j = len(f) // 2
    k = int(f[:j + 1])
    el = int(f[j:])
    fi = abs(el - k) * 4
    s = str(fi)
    i = int(int(hr) / 2) + 2
    m = ''
    for g2 in range(j + 1):
        for h in range(1, 5):
            n = int(lc[g2 + h]) + int(s[g2 % len(s)])
            if n >= i:
                n -= i
            m += str(n)
    return m

def kvs_decode(vu, lc, hr='16'):
    if vu.startswith('function/'):
        vup = vu.split('/')
        uhash = vup[7][:2 * int(hr)]
        nchash = vup[7][2 * int(hr):]
        seed = calcseed(lc, hr)
        if seed and uhash:
            decoded = list(uhash)
            for k in range(len(uhash) - 1, -1, -1):
                el = k
                for m in range(k, len(seed)):
                    el += int(seed[m])
                el %= len(uhash)
                decoded[k], decoded[el] = decoded[el], decoded[k]
            vup[7] = ''.join(decoded) + nchash
        vu = '/'.join(vup[2:])
    return vu