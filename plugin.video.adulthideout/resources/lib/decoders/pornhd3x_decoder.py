import random
import string
import hashlib
import json
import re

def get_stream_url(episode_id, session, base_url="https://pornhd3x.tv"):
    """
    Retrieves the playable video stream array from the given PornHD3X video page.
    Args:
        episode_id (str): The Z7C2TLMT5N4KJXN8 id found on the video page.
        session (requests.Session): The requests session with the current Cloudflare cookies.
        base_url (str): The base domain.
    Returns:
        d (dict): A dictionary containing 'playlist' elements or None.
    """
    token = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    
    # This is the thfq constant extracted from fix.js
    thfq = "n1sqcua67bcq9826avrbi6m49vd7shxkn985mhodk06twz87wwxtp3dqiicks2dfyud213k6ygiomq01s94e4tr9v0k887bkyud213k6ygiomq01s94e4tr9v0k887bkqocxzw39esdyfhvtkpzq9n4e7at4kc6k8sxom08bl4dukp16h09oplu7zov4m5f8"
    
    c_name = thfq[13:37] + episode_id + thfq[40:64]
    
    # Set the cookie required by the player API
    domain = base_url.replace("https://", "").replace("http://", "").split('/')[0]
    session.cookies.set(c_name, token, domain=domain, path='/')
    
    # We must also try to set it for naked domain just in case it runs without www
    clean_domain = re.sub(r'^www\d*\.', '', domain)
    if clean_domain != domain:
         session.cookies.set(c_name, token, domain=clean_domain, path='/')

    hash_str = episode_id + token + "98126avrbi6m49vd7shxkn985"
    hash_md5 = hashlib.md5(hash_str.encode('utf-8')).hexdigest()
    
    api_url = f"{base_url}/ajax/get_sources/{episode_id}/{hash_md5}?count=1&mobile=false"
    
    headers = {
        'X-Requested-With': 'XMLHttpRequest',
        'Accept': 'application/json, text/javascript, */*; q=0.01'
    }
    
    try:
        response = session.get(api_url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        import xbmc
        xbmc.log(f"PornHD3X Decoder error: {e}", xbmc.LOGERROR)
        
    return None
