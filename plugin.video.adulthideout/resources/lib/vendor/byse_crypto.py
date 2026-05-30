# -*- coding: utf-8 -*-
"""
Pure-Python minimal implementation of SECP256R1 (P-256) ECDSA and AES-GCM
designed to make AdultHideout's PremiumPorn scraper 100% zero-dependency.
"""
import hashlib
import os

try:
    import xbmc
    xbmc.log("[AdultHideout] === SUCCESS === Loaded zero-dependency byse_crypto.py from lib/vendor!", level=xbmc.LOGINFO)
except Exception:
    pass

# --- Elliptic Curve SECP256R1 (P-256) Arithmetic ---
P256_P = 115792089210356248762697446949407573530086143415290314195533631308867097853951
P256_A = -3
P256_B = 0x5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b
P256_GX = 0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296
P256_GY = 0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5
P256_N = 115792089210356248762697446949407573529996955224135760342422259061068512044369

def ext_gcd(a, b):
    if a == 0:
        return b, 0, 1
    g, y, x = ext_gcd(b % a, a)
    return g, x - (b // a) * y, y

def mod_inv(a, m):
    a = a % m
    g, x, y = ext_gcd(a, m)
    if g != 1:
        raise ValueError("modular inverse does not exist")
    return x % m

def point_add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2:
        if (y1 + y2) % P256_P == 0:
            return None
        return point_double(p1)
    m = ((y2 - y1) * mod_inv(x2 - x1, P256_P)) % P256_P
    x3 = (m * m - x1 - x2) % P256_P
    y3 = (m * (x1 - x3) - y1) % P256_P
    return (x3, y3)

def point_double(p):
    if p is None:
        return None
    x, y = p
    if y == 0:
        return None
    m = ((3 * x * x + P256_A) * mod_inv(2 * y, P256_P)) % P256_P
    x3 = (m * m - 2 * x) % P256_P
    y3 = (m * (x - x3) - y) % P256_P
    return (x3, y3)

def jacobian_double(x, y, z):
    if y == 0 or z == 0:
        return 0, 0, 0
    ysq = (y * y) % P256_P
    s = (4 * x * ysq) % P256_P
    zsq = (z * z) % P256_P
    m = (3 * (x - zsq) * (x + zsq)) % P256_P
    x3 = (m * m - 2 * s) % P256_P
    y3 = (m * (s - x3) - 8 * ysq * ysq) % P256_P
    z3 = (2 * y * z) % P256_P
    return x3, y3, z3

def jacobian_add(x1, y1, z1, x2, y2, z2):
    if z1 == 0:
        return x2, y2, z2
    if z2 == 0:
        return x1, y1, z1
    z1sq = (z1 * z1) % P256_P
    z2sq = (z2 * z2) % P256_P
    u1 = (x1 * z2sq) % P256_P
    u2 = (x2 * z1sq) % P256_P
    s1 = (y1 * z2sq * z2) % P256_P
    s2 = (y2 * z1sq * z1) % P256_P
    if u1 == u2:
        if s1 == s2:
            return jacobian_double(x1, y1, z1)
        else:
            return 0, 0, 0
    h = (u2 - u1) % P256_P
    r = (s2 - s1) % P256_P
    h2 = (h * h) % P256_P
    h3 = (h2 * h) % P256_P
    x3 = (r * r - h3 - 2 * u1 * h2) % P256_P
    y3 = (r * (u1 * h2 - x3) - s1 * h3) % P256_P
    z3 = (z1 * z2 * h) % P256_P
    return x3, y3, z3

def point_mul(k, p):
    if p is None:
        return None
    x, y = p
    rx, ry, rz = 0, 0, 0
    ax, ay, az = x, y, 1
    while k > 0:
        if k & 1:
            rx, ry, rz = jacobian_add(rx, ry, rz, ax, ay, az)
        ax, ay, az = jacobian_double(ax, ay, az)
        k >>= 1
    if rz == 0:
        return None
    zinv = mod_inv(rz, P256_P)
    zinv2 = (zinv * zinv) % P256_P
    zinv3 = (zinv2 * zinv) % P256_P
    return (rx * zinv2) % P256_P, (ry * zinv3) % P256_P

def generate_keypair():
    # Private key d in [1, n-1]
    d = int.from_bytes(os.urandom(32), "big") % (P256_N - 1) + 1
    pub = point_mul(d, (P256_GX, P256_GY))
    return d, pub

def sign_challenge(challenge_bytes, private_key_int):
    h = hashlib.sha256(challenge_bytes).digest()
    z = int.from_bytes(h, "big")
    while True:
        k = int.from_bytes(os.urandom(32), "big") % (P256_N - 1) + 1
        p = point_mul(k, (P256_GX, P256_GY))
        if p is None:
            continue
        rx, ry = p
        r = rx % P256_N
        if r == 0:
            continue
        s = (mod_inv(k, P256_N) * (z + r * private_key_int)) % P256_N
        if s != 0:
            break
    return r, s


# --- AES block cipher (Encryption Only) ---
sbox = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
]

def xtime(a):
    return ((a << 1) ^ 0x1B) & 0xFF if a & 0x80 else (a << 1) & 0xFF

def mix_single_column(col):
    a, b, c, d = col
    t = a ^ b ^ c ^ d
    u = a
    a_new = a ^ t ^ xtime(a ^ b)
    b_new = b ^ t ^ xtime(b ^ c)
    c_new = c ^ t ^ xtime(c ^ d)
    d_new = d ^ t ^ xtime(d ^ u)
    return a_new, b_new, c_new, d_new

def expand_key(key):
    nk = len(key) // 4
    nr = nk + 6
    w = list(key)
    rcon = [0, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]
    i = nk
    while len(w) < 4 * 4 * (nr + 1):
        temp = w[-4:]
        if i % nk == 0:
            temp = temp[1:] + temp[:1]  # RotWord
            temp = [sbox[b] for b in temp]  # SubWord
            temp[0] ^= rcon[i // nk]  # XOR Rcon
        elif nk > 6 and i % nk == 4:
            temp = [sbox[b] for b in temp]  # SubWord
        prev = w[-4 * nk : -4 * nk + 4]
        next_word = [prev[x] ^ temp[x] for x in range(4)]
        w.extend(next_word)
        i += 1
    return w

def aes_encrypt(block, round_keys, nr):
    state = list(block)
    # AddRoundKey (round 0)
    for j in range(16):
        state[j] ^= round_keys[j]
    # Rounds 1 to Nr-1
    for r in range(1, nr):
        # SubBytes
        for j in range(16):
            state[j] = sbox[state[j]]
        # ShiftRows
        state[1], state[5], state[9], state[13] = state[5], state[9], state[13], state[1]
        state[2], state[6], state[10], state[14] = state[10], state[14], state[2], state[6]
        state[3], state[7], state[11], state[15] = state[15], state[3], state[7], state[11]
        # MixColumns
        for col_idx in range(0, 16, 4):
            state[col_idx : col_idx + 4] = mix_single_column(state[col_idx : col_idx + 4])
        # AddRoundKey
        rk_offset = r * 16
        for j in range(16):
            state[j] ^= round_keys[rk_offset + j]
    # Final Round (round Nr)
    # SubBytes
    for j in range(16):
        state[j] = sbox[state[j]]
    # ShiftRows
    state[1], state[5], state[9], state[13] = state[5], state[9], state[13], state[1]
    state[2], state[6], state[10], state[14] = state[10], state[14], state[2], state[6]
    state[3], state[7], state[11], state[15] = state[15], state[3], state[7], state[11]
    # AddRoundKey
    rk_offset = nr * 16
    for j in range(16):
        state[j] ^= round_keys[rk_offset + j]
    return bytes(state)


# --- AES-GCM Authenticated Decryption ---
def gf_2_128_mul(x, y):
    res = 0
    for i in range(128):
        if (y >> (127 - i)) & 1:
            res ^= x
        if x & 1:
            x = (x >> 1) ^ 0xE1000000000000000000000000000000
        else:
            x >>= 1
    return res

def ghash(h, data):
    y = 0
    for i in range(0, len(data), 16):
        block = data[i:i+16]
        if len(block) < 16:
            block = block + b"\x00" * (16 - len(block))
        x = int.from_bytes(block, "big")
        y ^= x
        y = gf_2_128_mul(y, h)
    return y

def gcm_decrypt(key, iv, ciphertext, tag, aad=b""):
    try:
        import xbmc
        xbmc.log("[AdultHideout] === SUCCESS === decrypting GCM using pure-Python byse_crypto.py in lib/vendor!", level=xbmc.LOGINFO)
    except Exception:
        pass
    round_keys = expand_key(key)
    nr = len(key) // 4 + 6
    # Compute hash key H
    h_bytes = aes_encrypt(b"\x00" * 16, round_keys, nr)
    h = int.from_bytes(h_bytes, "big")
    # Determine initial counter J0
    if len(iv) == 12:
        j0 = iv + b"\x00\x00\x00\x01"
    else:
        len_iv_bits = (len(iv) * 8).to_bytes(8, "big")
        j0_hash = ghash(h, iv + b"\x00" * ((16 - len(iv) % 16) % 16) + b"\x00" * 8 + len_iv_bits)
        j0 = j0_hash.to_bytes(16, "big")
    # CTR Mode decryption
    decrypted = bytearray()
    j0_int = int.from_bytes(j0, "big")
    ctr_int = (j0_int + 1) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    for i in range(0, len(ciphertext), 16):
        block = ciphertext[i:i+16]
        ctr_bytes = ctr_int.to_bytes(16, "big")
        keystream_block = aes_encrypt(ctr_bytes, round_keys, nr)
        for b_idx in range(len(block)):
            decrypted.append(block[b_idx] ^ keystream_block[b_idx])
        ctr_int = (ctr_int + 1) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    # Verify Authentication Tag
    aad_len_bytes = (len(aad) * 8).to_bytes(8, "big")
    ct_len_bytes = (len(ciphertext) * 8).to_bytes(8, "big")
    aad_padded = aad + b"\x00" * ((16 - len(aad) % 16) % 16)
    ct_padded = ciphertext + b"\x00" * ((16 - len(ciphertext) % 16) % 16)
    hash_input = aad_padded + ct_padded + aad_len_bytes + ct_len_bytes
    s = ghash(h, hash_input)
    j0_encrypted = aes_encrypt(j0, round_keys, nr)
    s_bytes = s.to_bytes(16, "big")
    expected_tag = bytes(j0_encrypted[k] ^ s_bytes[k] for k in range(16))
    if tag != expected_tag:
        raise ValueError("Authentication tag verification failed!")
    return bytes(decrypted)


# --- AES-CBC & PBKDF2-SHA512 Zero-Dependency Support ---
inv_sbox = [
    0x52, 0x09, 0x6a, 0xd5, 0x30, 0x36, 0xa5, 0x38, 0xbf, 0x40, 0xa3, 0x9e, 0x81, 0xf3, 0xd7, 0xfb,
    0x7c, 0xe3, 0x39, 0x82, 0x9b, 0x2f, 0xff, 0x87, 0x34, 0x8e, 0x43, 0x44, 0xc4, 0xde, 0xe9, 0xcb,
    0x54, 0x7b, 0x94, 0x32, 0xa6, 0xc2, 0x23, 0x3d, 0xee, 0x4c, 0x95, 0x0b, 0x42, 0xfa, 0xc3, 0x4e,
    0x08, 0x2e, 0xa1, 0x66, 0x28, 0xd9, 0x24, 0xb2, 0x76, 0x5b, 0xa2, 0x49, 0x6d, 0x8b, 0xd1, 0x25,
    0x72, 0xf8, 0xf6, 0x64, 0x86, 0x68, 0x98, 0x16, 0xd4, 0xa4, 0x5c, 0xcc, 0x5d, 0x65, 0xb6, 0x92,
    0x6c, 0x70, 0x48, 0x50, 0xfd, 0xed, 0xb9, 0xda, 0x5e, 0x15, 0x46, 0x57, 0xa7, 0x8d, 0x9d, 0x84,
    0x90, 0xd8, 0xab, 0x00, 0x8c, 0xbc, 0xd3, 0x0a, 0xf7, 0xe4, 0x58, 0x05, 0xb8, 0xb3, 0x45, 0x06,
    0xd0, 0x2c, 0x1e, 0x8f, 0xca, 0x3f, 0x0f, 0x02, 0xc1, 0xaf, 0xbd, 0x03, 0x01, 0x13, 0x8a, 0x6b,
    0x3a, 0x91, 0x11, 0x41, 0x4f, 0x67, 0xdc, 0xea, 0x97, 0xf2, 0xcf, 0xce, 0xf0, 0xb4, 0xe6, 0x73,
    0x96, 0xac, 0x74, 0x22, 0xe7, 0xad, 0x35, 0x85, 0xe2, 0xf9, 0x37, 0xe8, 0x1c, 0x75, 0xdf, 0x6e,
    0x47, 0xf1, 0x1a, 0x71, 0x1d, 0x29, 0xc5, 0x89, 0x6f, 0xb7, 0x62, 0x0e, 0xaa, 0x18, 0xbe, 0x1b,
    0xfc, 0x56, 0x3e, 0x4b, 0xc6, 0xd2, 0x79, 0x20, 0x9a, 0xdb, 0xc0, 0xfe, 0x78, 0xcd, 0x5a, 0xf4,
    0x1f, 0xdd, 0xa8, 0x33, 0x88, 0x07, 0xc7, 0x31, 0xb1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xec, 0x5f,
    0x60, 0x51, 0x7f, 0xa9, 0x19, 0xb5, 0x4a, 0x0d, 0x2d, 0xe5, 0x7a, 0x9f, 0x93, 0xc9, 0x9c, 0xef,
    0xa0, 0xe0, 0x3b, 0x4d, 0xae, 0x2a, 0xf5, 0xb0, 0xc8, 0xeb, 0xbb, 0x3c, 0x83, 0x53, 0x99, 0x61,
    0x17, 0x2b, 0x04, 0x7e, 0xba, 0x77, 0xd6, 0x26, 0xe1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0c, 0x7d
]

def gf_mul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p

def inv_mix_single_column(col):
    a, b, c, d = col
    a_new = gf_mul(a, 14) ^ gf_mul(b, 11) ^ gf_mul(c, 13) ^ gf_mul(d, 9)
    b_new = gf_mul(a, 9) ^ gf_mul(b, 14) ^ gf_mul(c, 11) ^ gf_mul(d, 13)
    c_new = gf_mul(a, 13) ^ gf_mul(b, 9) ^ gf_mul(c, 14) ^ gf_mul(d, 11)
    d_new = gf_mul(a, 11) ^ gf_mul(b, 13) ^ gf_mul(c, 9) ^ gf_mul(d, 14)
    return a_new, b_new, c_new, d_new

def aes_decrypt(block, round_keys, nr):
    state = list(block)
    # AddRoundKey (round Nr)
    rk_offset = nr * 16
    for j in range(16):
        state[j] ^= round_keys[rk_offset + j]
    # Rounds Nr-1 down to 1
    for r in range(nr - 1, 0, -1):
        # InvShiftRows
        state[1], state[5], state[9], state[13] = state[13], state[1], state[5], state[9]
        state[2], state[6], state[10], state[14] = state[10], state[14], state[2], state[6]
        state[3], state[7], state[11], state[15] = state[7], state[11], state[15], state[3]
        # InvSubBytes
        for j in range(16):
            state[j] = inv_sbox[state[j]]
        # AddRoundKey
        rk_offset = r * 16
        for j in range(16):
            state[j] ^= round_keys[rk_offset + j]
        # InvMixColumns
        for col_idx in range(0, 16, 4):
            state[col_idx : col_idx + 4] = inv_mix_single_column(state[col_idx : col_idx + 4])
    # Final Round (round 0)
    # InvShiftRows
    state[1], state[5], state[9], state[13] = state[13], state[1], state[5], state[9]
    state[2], state[6], state[10], state[14] = state[10], state[14], state[2], state[6]
    state[3], state[7], state[11], state[15] = state[7], state[11], state[15], state[3]
    # InvSubBytes
    for j in range(16):
        state[j] = inv_sbox[state[j]]
    # AddRoundKey
    for j in range(16):
        state[j] ^= round_keys[j]
    return bytes(state)

def cbc_decrypt(key, iv, ciphertext):
    try:
        import xbmc
        xbmc.log("[AdultHideout] === SUCCESS === decrypting CBC using pure-Python byse_crypto.py in lib/vendor!", level=xbmc.LOGINFO)
    except Exception:
        pass
    round_keys = expand_key(key)
    nr = len(key) // 4 + 6
    decrypted = bytearray()
    prev_block = iv
    for i in range(0, len(ciphertext), 16):
        block = ciphertext[i:i+16]
        decrypted_block = aes_decrypt(block, round_keys, nr)
        for j in range(16):
            decrypted.append(decrypted_block[j] ^ prev_block[j])
        prev_block = block
    return bytes(decrypted)

def pbkdf2_sha512(password, salt, dklen, count):
    import hmac
    def prf(k, m):
        return hmac.new(k, m, hashlib.sha512).digest()
    result = bytearray()
    block_num = 1
    while len(result) < dklen:
        rv = prf(password, salt + block_num.to_bytes(4, "big"))
        tmp = bytearray(rv)
        for _ in range(count - 1):
            rv = prf(password, rv)
            for idx in range(len(tmp)):
                tmp[idx] ^= rv[idx]
        result.extend(tmp)
        block_num += 1
    return bytes(result[:dklen])

def pkcs7_unpad(data, block_size=16):
    padding_len = data[-1]
    if padding_len < 1 or padding_len > block_size:
        raise ValueError("Invalid padding length")
    for i in range(len(data) - padding_len, len(data)):
        if data[i] != padding_len:
            raise ValueError("Invalid padding byte")
    return data[:-padding_len]
