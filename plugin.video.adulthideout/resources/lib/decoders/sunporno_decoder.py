#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sunporno URL Decoder
"""

import re
import time

def calcseed(lc, hr='16'):
    """
    Calculate seed from license code.
    Logic derived from player JS (v7.11.2).
    """
    if not lc:
        return None
        
    try:
        # Expects lc with '$' prefix, e.g. '$536403617696893'
        if not lc.startswith('$'):
            # If no $, assume it's the raw digits and prepend $
            lc = '$' + lc
            
        f_raw = lc[1:].replace('0', '1')
        j = len(f_raw) // 2
        k = int(f_raw[:j + 1])
        el = int(f_raw[j:])
        fi = abs(el - k) * 4
        s = str(fi)
        
        i = int(int(hr) / 2) + 2
        m = ''
        for g in range(j + 1):
            for h in range(1, 5):
                if g + h < len(lc):
                    val_d = int(lc[g + h])
                    val_f = int(s[g % len(s)])
                    n = val_d + val_f
                    if n >= i:
                        n -= i
                    m += str(n)
        return m
    except Exception:
        return None

def decode_video_url(video_url, license_code=None):
    """
    Decodes the Sunporno video URL using KVS permutation logic.
    Supports versions where only the first 32 characters are permuted.
    """
    if not video_url:
        return None
        
    should_permute = False
    
    if video_url.startswith("function/"):
        try:
             # Strip prefix to get base URL
             # Pattern: function/ID/URL
             match = re.search(r'function/\d+/(https?://.+)$', video_url)
             if match:
                 video_url = match.group(1)
             else:
                 parts = video_url.split('/')
                 if len(parts) >= 3:
                     video_url = parts[2].rstrip('/')
                     if video_url.startswith('/'): 
                         video_url = 'https:' + video_url
             should_permute = True
        except Exception:
             pass
    elif license_code and ('/get_file/' in video_url or '/video/' in video_url):
        # Raw URL with license code available -> Try permute
        should_permute = True

    # Apply Permutation logic
    if should_permute and license_code:
        try:
             # Use default hr=16 as per KVS standard
             seed = calcseed(license_code, '16')
             
             if seed:
                 parts_new = video_url.split('/')
                 hash_idx = -1
                 # Find the hash part
                 for idx, p in enumerate(parts_new):
                     # Clean non-hex chars like in the earlier fix
                     p_clean = re.sub(r'[^a-fA-F0-9]', '', p)
                     # In newer KVS versions, hashes can be 40 or 42 chars (or more)
                     if len(p_clean) >= 32:
                         # ONLY PERMUTE FIRST 32 CHARS as per KVS JS v7.11.2
                         h_original = p_clean[:32]
                         tail = p_clean[32:]
                         
                         target_hash = list(h_original)
                         key_digits = [int(d) for d in seed]
                         
                         # Reverse loop is CRITICAL
                         for i_h in range(len(target_hash) - 1, -1, -1):
                             g = i_h
                             for i_s in range(i_h, len(key_digits)):
                                 g += key_digits[i_s]
                             g = g % len(target_hash)
                             target_hash[i_h], target_hash[g] = target_hash[g], target_hash[i_h]
                         
                         parts_new[idx] = "".join(target_hash) + tail
                         hash_idx = idx
                         break
                 
                 if hash_idx != -1:
                     video_url = "/".join(parts_new)
        except Exception:
            pass
            
    # Basic cleanup
    if video_url:
        video_url = video_url.strip().rstrip('/')
        if not video_url.startswith('http'):
            if video_url.startswith('//'):
                video_url = 'https:' + video_url
            
    return video_url

class SunpornoDecoder:
    def __init__(self, logger=None):
        self.logger = logger

    def _log(self, msg):
        if self.logger:
            if hasattr(self.logger, 'log'):
                self.logger.log(msg)
            else:
                print(msg)

    def decode_embed(self, html):
        """
        Extracts and decodes video information from a Sunporno embed page.
        """
        if not html:
            return None
            
        result = {'video_url': None, 'rnd': None, 'license_code': None}
            
        try:
            # 1. Extract license_code, rnd and video_url using multiple patterns
            lc_match = re.search(r'license_code:\s*\'([^\']+)\'', html)
            if not lc_match:
                lc_match = re.search(r'license_code["\']?\s*:\s*["\']?([^"\',}]+)', html)
            
            if lc_match:
                result['license_code'] = lc_match.group(1).replace("'", "").replace('"', "").strip()
                self._log(f"Found license_code: {result['license_code']}")
            
            rnd_match = re.search(r'rnd:\s*\'(\d+)\'', html)
            if not rnd_match:
                rnd_match = re.search(r'rnd["\']?\s*:\s*["\']?(\d+)', html)
            
            if rnd_match:
                result['rnd'] = rnd_match.group(1)
                self._log(f"Found rnd: {result['rnd']}")
            
            video_url = None
            url_match = re.search(r'video_url:\s*\'([^\']+)\'', html)
            if not url_match:
                 url_match = re.search(r'video_url["\']?\s*:\s*["\']?([^"\',}]+)', html)
            
            if url_match:
                video_url = url_match.group(1).replace('\\/', '/').replace("'", "").replace('"', "").strip()
                self._log(f"Extracted raw video_url: {video_url}")
            
            if video_url:
                decoded = decode_video_url(video_url, result['license_code'])
                if decoded:
                    self._log(f"Decoded video_url: {decoded}")
                    result['video_url'] = decoded
            
            # Fallbacks
            if not result['video_url'] and video_url:
                result['video_url'] = video_url
                
            if result['video_url']:
                return result
                
        except Exception as e:
            self._log(f"Decoder Exception: {e}")
            
        return None

    def decode(self, content, logger=None):
        """
        Legacy decode method if called from sunporno.py
        """
        if logger:
            self.logger = logger
        return self.decode_embed(content)
