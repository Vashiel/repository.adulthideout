"""
KVS (Kernel Video Sharing) Video URL Decoder

Decodes obfuscated video URLs from KVS-powered video sites.
Ported from yt-dlp's generic.py extractor.

Usage:
    from resources.lib.decoders.kvs_decoder import kvs_decode_url
    
    decoded_url = kvs_decode_url(video_url, license_code)
"""
import urllib.parse


def kvs_get_license_token(license_code):
    """
    Generate license token array from license_code.
    
    Args:
        license_code: License code from flashvars (e.g., '$624178720592748')
    
    Returns:
        List of 32 integers used for URL decoding
    """
    license_code = license_code.replace('$', '')
    license_values = [int(char) for char in license_code]
    
    modlicense = license_code.replace('0', '1')
    center = len(modlicense) // 2
    fronthalf = int(modlicense[:center + 1])
    backhalf = int(modlicense[center:])
    modlicense = str(4 * abs(fronthalf - backhalf))[:center + 1]
    
    return [
        (license_values[index + offset] + current) % 10
        for index, current in enumerate(map(int, modlicense))
        for offset in range(4)
    ]


def kvs_decode_url(video_url, license_code):
    """
    Decode obfuscated KVS video URL.
    
    Args:
        video_url: Obfuscated URL (starts with 'function/0/')
        license_code: License code from flashvars
    
    Returns:
        Decoded video URL
    """
    if not video_url.startswith('function/0/'):
        return video_url  # not obfuscated
    
    parsed = urllib.parse.urlparse(video_url[len('function/0/'):])
    license_token = kvs_get_license_token(license_code)
    urlparts = parsed.path.split('/')
    
    HASH_LENGTH = 32
    if len(urlparts) > 3 and len(urlparts[3]) >= HASH_LENGTH:
        hash_ = urlparts[3][:HASH_LENGTH]
        indices = list(range(HASH_LENGTH))
        
        # Swap indices of hash according to the license token
        accum = 0
        for src in reversed(range(HASH_LENGTH)):
            accum += license_token[src]
            dest = (src + accum) % HASH_LENGTH
            indices[src], indices[dest] = indices[dest], indices[src]
        
        urlparts[3] = ''.join(hash_[index] for index in indices) + urlparts[3][HASH_LENGTH:]
    
    return urllib.parse.urlunparse(parsed._replace(path='/'.join(urlparts)))
