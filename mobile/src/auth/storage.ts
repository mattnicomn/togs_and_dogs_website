import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'usr_id_token';
const SESSION_KEY = 'usr_session_data';
const REFRESH_TOKEN_KEY = 'usr_refresh_token';

export const saveIdToken = async (token: string): Promise<void> => {
  try {
    await SecureStore.setItemAsync(TOKEN_KEY, token);
  } catch (e: any) {
    throw new Error(`SecureStore set ID token failed: ${e.message || e}`);
  }
};

export const getIdToken = async (): Promise<string | null> => {
  try {
    return await SecureStore.getItemAsync(TOKEN_KEY);
  } catch (e: any) {
    throw new Error(`SecureStore get ID token failed: ${e.message || e}`);
  }
};

export const clearIdToken = async (): Promise<void> => {
  try {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  } catch (e: any) {
    throw new Error(`SecureStore delete ID token failed: ${e.message || e}`);
  }
};

export const saveRefreshToken = async (token: string): Promise<void> => {
  try {
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, token);
  } catch (e: any) {
    throw new Error(`SecureStore set refresh token failed: ${e.message || e}`);
  }
};

export const getRefreshToken = async (): Promise<string | null> => {
  try {
    return await SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
  } catch (e: any) {
    throw new Error(`SecureStore get refresh token failed: ${e.message || e}`);
  }
};

export const clearRefreshToken = async (): Promise<void> => {
  try {
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY);
  } catch (e: any) {
    throw new Error(`SecureStore delete refresh token failed: ${e.message || e}`);
  }
};

export const saveSessionData = async (data: string): Promise<void> => {
  try {
    await SecureStore.setItemAsync(SESSION_KEY, data);
  } catch (e: any) {
    throw new Error(`SecureStore set session data failed: ${e.message || e}`);
  }
};

export const getSessionData = async (): Promise<string | null> => {
  try {
    return await SecureStore.getItemAsync(SESSION_KEY);
  } catch (e: any) {
    throw new Error(`SecureStore get session data failed: ${e.message || e}`);
  }
};

export const clearSessionData = async (): Promise<void> => {
  try {
    await SecureStore.deleteItemAsync(SESSION_KEY);
  } catch (e: any) {
    throw new Error(`SecureStore delete session data failed: ${e.message || e}`);
  }
};

export const isTokenExpired = (token: string): boolean => {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;
    
    const decodeBase64 = (str: string): string => {
      let base64 = str.replace(/-/g, '+').replace(/_/g, '/');
      const pad = base64.length % 4;
      if (pad) {
        if (pad === 1) return '';
        base64 += new Array(5 - pad).join('=');
      }
      
      if (typeof atob !== 'undefined') {
        return atob(base64);
      }
      
      // Fallback manual decoder if atob is not defined
      const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
      const lookup = new Uint8Array(256);
      for (let i = 0; i < chars.length; i++) {
        lookup[chars.charCodeAt(i)] = i;
      }
      
      let bufferLength = base64.length * 0.75;
      if (base64[base64.length - 1] === '=') {
        bufferLength--;
        if (base64[base64.length - 2] === '=') {
          bufferLength--;
        }
      }
      
      const bytes = new Uint8Array(bufferLength);
      let p = 0;
      for (let i = 0; i < base64.length; i += 4) {
        const encoded1 = lookup[base64.charCodeAt(i)];
        const encoded2 = lookup[base64.charCodeAt(i + 1)];
        const encoded3 = lookup[base64.charCodeAt(i + 2)];
        const encoded4 = lookup[base64.charCodeAt(i + 3)];
        
        bytes[p++] = (encoded1 << 2) | (encoded2 >> 4);
        if (p < bufferLength) {
          bytes[p++] = ((encoded2 & 15) << 4) | (encoded3 >> 2);
        }
        if (p < bufferLength) {
          bytes[p++] = ((encoded3 & 3) << 6) | (encoded4 & 63);
        }
      }
      
      let out = '';
      for (let i = 0; i < bytes.length; i++) {
        out += String.fromCharCode(bytes[i]);
      }
      return out;
    };
    
    const payloadStr = decodeBase64(parts[1]);
    const payload = JSON.parse(payloadStr);
    if (!payload || typeof payload.exp !== 'number') return true;
    
    const nowSeconds = Math.floor(Date.now() / 1000);
    // Return true if token expires in less than 60 seconds
    return payload.exp - nowSeconds < 60;
  } catch (e) {
    console.warn('Failed to parse JWT token expiration', e);
    return true;
  }
};
