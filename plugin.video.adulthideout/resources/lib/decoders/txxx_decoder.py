#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
import urllib.parse

class TxxxDecoder:
    
    def _clean_b64_string(self, b64_string):
        if not b64_string or len(b64_string) == 0:
            return None
        
        replacements = {
            '\u0410': 'A', '\u0412': 'B', '\u0421': 'C', '\u0415': 'E', '\u041d': 'H', '\u041a': 'K',
            '\u041c': 'M', '\u041e': 'O', '\u0420': 'P', '\u0422': 'T', '\u0425': 'X',
            '\u0430': 'a', '\u0441': 'c', '\u0435': 'e', '\u043a': 'k', '\u043e': 'o',
            '\u0440': 'p', '\u0445': 'x', '\u0443': 'y', '~': '=',
            '\u0416': 'W', '\u0417': '3', '\u0418': 'B', '\u041b': 'JI', '\u0423': 'Y', '\u0424': '4',
            '\u0427': 'X', '\u042f': '9', '\u0431': '6', '\u0432': 'B', '\u0433': 'r', '\u0434': 'A',
            '\u0436': 'q', '\u0437': '7', '\u0438': 'u', '\u043b': 'JI', '\u0442': 'b', '\u0444': 'O',
            '\u0447': 'x', '\u044f': 'q'
        }
        for original, replacement in replacements.items():
            b64_string = b64_string.replace(original, replacement)
        
        b64_string = b64_string.replace('\n', '').replace('\r', '').replace('\t', '')
        return b64_string

    def decode_stream_url(self, encoded_path_raw, base_url, video_page_url, logger):
        try:
            encoded_path_replaced = self._clean_b64_string(encoded_path_raw)
            path_b64, params_b64 = "", ""
            if ',' in encoded_path_replaced:
                path_b64, params_b64 = encoded_path_replaced.split(',', 1)
            else:
                path_b64 = encoded_path_replaced

            valid_b64_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/='
            path_b64_cleaned = ''.join(c for c in path_b64 if c in valid_b64_chars)
            
            missing_padding = len(path_b64_cleaned) % 4
            if missing_padding:
                path_b64_cleaned += '=' * (4 - missing_padding)

            decoded_path = base64.b64decode(path_b64_cleaned).decode('utf-8', 'ignore').strip()
            full_stream_url = urllib.parse.urljoin(base_url, decoded_path)

            if params_b64:
                params_b64_cleaned = ''.join(c for c in params_b64 if c in valid_b64_chars)
                missing_padding = len(params_b64_cleaned) % 4
                if missing_padding:
                    params_b64_cleaned += '=' * (4 - missing_padding)
                
                decoded_params = base64.b64decode(params_b64_cleaned).decode('utf-8', 'ignore').strip()
                full_stream_url += '?' + decoded_params
            
            return f"{full_stream_url}|Referer={video_page_url}"

        except Exception as e: 
            if logger:
                logger.error(f"Decoder failed: {e}")
            return None