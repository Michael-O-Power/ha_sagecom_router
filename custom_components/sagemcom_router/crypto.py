 
import hashlib

def _pure_sha512_crypt(key: str, salt: str) -> str:
    """Pure python implementation of Unix SHA512 crypt to avoid missing 'crypt' module in Python 3.13+."""
    key_b = key.encode('utf-8')
    salt_b = salt.encode('utf-8')
    ctx_a = hashlib.sha512(key_b + salt_b)
    ctx_b = hashlib.sha512(key_b + salt_b + key_b)
    dgst_b = ctx_b.digest()
    key_len = len(key_b)
    
    for i in range(0, key_len, 64):
        ctx_a.update(dgst_b[:min(64, key_len - i)])
    k = key_len
    while k > 0:
        if k & 1:
            ctx_a.update(dgst_b)
        else:
            ctx_a.update(key_b)
        k >>= 1
    dgst_a = ctx_a.digest()
    ctx_dp = hashlib.sha512(key_b * key_len)
    dgst_dp = ctx_dp.digest()
    p_bytes = bytearray()
    
    for i in range(0, key_len, 64):
        p_bytes.extend(dgst_dp[:min(64, key_len - i)])
    ctx_ds = hashlib.sha512(salt_b * (16 + dgst_a[0]))
    dgst_ds = ctx_ds.digest()
    salt_len = len(salt_b)
    s_bytes = bytearray()
    
    for i in range(0, salt_len, 64):
        s_bytes.extend(dgst_ds[:min(64, salt_len - i)])
    dgst = dgst_a
    
    for i in range(5000):
        ctx_c = hashlib.sha512()
        if i % 2 != 0:
            ctx_c.update(p_bytes)
        else:
            ctx_c.update(dgst)
        if i % 3 != 0:
            ctx_c.update(s_bytes)
        if i % 7 != 0:
            ctx_c.update(p_bytes)
        if i % 2 != 0:
            ctx_c.update(dgst)
        else:
            ctx_c.update(p_bytes)
        dgst = ctx_c.digest()
        
    b64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    def _b64_from_24bit(b2, b1, b0, n):
        w = (b2 << 16) | (b1 << 8) | b0
        return "".join(b64[(w >> (6 * i)) & 0x3f] for i in range(n))
        
    order = [
        (0, 21, 42), (22, 43, 1), (44, 2, 23), (3, 24, 45), (25, 46, 4),
        (47, 5, 26), (6, 27, 48), (28, 49, 7), (50, 8, 29), (9, 30, 51),
        (31, 52, 10), (53, 11, 32), (12, 33, 54), (34, 55, 13), (56, 14, 35),
        (15, 36, 57), (37, 58, 16), (59, 17, 38), (18, 39, 60), (40, 61, 19),
        (62, 20, 41)
    ]
    res = "".join(_b64_from_24bit(dgst[b2], dgst[b1], dgst[b0], 4) for b2, b1, b0 in order)
    res += _b64_from_24bit(0, 0, dgst[63], 2)
    return f"$6${salt}${res}"

def calculate_auth_key(username, password, salt, nonce, cnonce):
    """Replicate the customized F@st 5866T web-GUI SHA-512 signature generation."""
    f_val = _pure_sha512_crypt(password, salt)
    f_sub = f_val[3:]
    g_str = f"{username}:{nonce}:{f_sub}"
    g = hashlib.sha512(g_str.encode("utf-8")).hexdigest()
    auth_string = f"{g}:0:{cnonce}"
    return hashlib.sha512(auth_string.encode("utf-8")).hexdigest()
