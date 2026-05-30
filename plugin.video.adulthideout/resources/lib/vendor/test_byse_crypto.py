import sys
sys.path.insert(0, r"C:\Users\Serdar\AppData\Roaming\Kodi\addons\plugin.video.adulthideout\resources\lib\vendor")

import byse_crypto
import os
import hashlib

print("--- Testing Self-Contained AES-GCM Decryption ---")
key = os.urandom(32)
iv = os.urandom(12)
aad = b"associated data"
plaintext = b"Hello, this is a secret Byse payload! We want to check GCM mode."

# CTR Encryption
round_keys = byse_crypto.expand_key(key)
nr = len(key) // 4 + 6
j0 = iv + b"\x00\x00\x00\x01"
ciphertext = bytearray()
j0_int = int.from_bytes(j0, "big")
ctr_int = (j0_int + 1) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
for i in range(0, len(plaintext), 16):
    block = plaintext[i:i+16]
    ctr_bytes = ctr_int.to_bytes(16, "big")
    keystream_block = byse_crypto.aes_encrypt(ctr_bytes, round_keys, nr)
    for b_idx in range(len(block)):
        ciphertext.append(block[b_idx] ^ keystream_block[b_idx])
    ctr_int = (ctr_int + 1) & 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
ciphertext = bytes(ciphertext)

# Compute GHASH and authentication tag
aad_len_bytes = (len(aad) * 8).to_bytes(8, "big")
ct_len_bytes = (len(ciphertext) * 8).to_bytes(8, "big")
aad_padded = aad + b"\x00" * ((16 - len(aad) % 16) % 16)
ct_padded = ciphertext + b"\x00" * ((16 - len(ciphertext) % 16) % 16)
hash_input = aad_padded + ct_padded + aad_len_bytes + ct_len_bytes
h_bytes = byse_crypto.aes_encrypt(b"\x00" * 16, round_keys, nr)
h = int.from_bytes(h_bytes, "big")
s = byse_crypto.ghash(h, hash_input)
j0_encrypted = byse_crypto.aes_encrypt(j0, round_keys, nr)
tag = bytes(j0_encrypted[k] ^ s.to_bytes(16, "big")[k] for k in range(16))

# Decrypt using our GCM decrypter
decrypted = byse_crypto.gcm_decrypt(key, iv, ciphertext, tag, aad)
print("GCM Decrypted successfully:", decrypted == plaintext)

print("\n--- Testing AES-CBC & PBKDF2-SHA512 Decryption ---")
password = "supersecretpassword"
salt = os.urandom(16)
iterations = 1000
dklen = 32
derived_key = byse_crypto.pbkdf2_sha512(password.encode("utf-8"), salt, dklen, iterations)
print("PBKDF2 Key Length:", len(derived_key))

# Test CBC Decryption
plaintext_cbc = b"This is a secret session key for OK.ru video player stream decryption!"
pad_len = 16 - (len(plaintext_cbc) % 16)
padded_plaintext_cbc = plaintext_cbc + bytes([pad_len] * pad_len)

# CBC Encryption (manual)
cbc_ciphertext = bytearray()
cbc_iv = os.urandom(16)
prev = cbc_iv
for i in range(0, len(padded_plaintext_cbc), 16):
    block = padded_plaintext_cbc[i:i+16]
    xor_block = bytes(block[j] ^ prev[j] for j in range(16))
    encrypted_block = byse_crypto.aes_encrypt(xor_block, byse_crypto.expand_key(derived_key), len(derived_key) // 4 + 6)
    cbc_ciphertext.extend(encrypted_block)
    prev = encrypted_block
cbc_ciphertext = bytes(cbc_ciphertext)

# Decrypt using cbc_decrypt
decrypted_cbc_padded = byse_crypto.cbc_decrypt(derived_key, cbc_iv, cbc_ciphertext)
decrypted_cbc = byse_crypto.pkcs7_unpad(decrypted_cbc_padded)
print("CBC Decrypted successfully:", decrypted_cbc == plaintext_cbc)

print("\n--- Testing Self-Contained SECP256R1 Key Generation, Signatures & Verification ---")
d, pub = byse_crypto.generate_keypair()
print("Private key d:", d)
print("Public Key Point (X, Y):", pub)
challenge = b"random challenge nonce"
r, s = byse_crypto.sign_challenge(challenge, d)
print("Generated Signature (r, s):", (r, s))

# Verify signature mathematically
e = int.from_bytes(hashlib.sha256(challenge).digest(), "big")
w = byse_crypto.mod_inv(s, byse_crypto.P256_N)
u1 = (e * w) % byse_crypto.P256_N
u2 = (r * w) % byse_crypto.P256_N
p1 = byse_crypto.point_mul(u1, (byse_crypto.P256_GX, byse_crypto.P256_GY))
p2 = byse_crypto.point_mul(u2, pub)
p3 = byse_crypto.point_add(p1, p2)

if p3 is not None and p3[0] % byse_crypto.P256_N == r:
    print("ECDSA signature verification: SUCCESS!")
else:
    print("ECDSA signature verification: FAILED!")
