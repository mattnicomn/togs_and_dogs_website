import { CognitoUserPool, CognitoUser, AuthenticationDetails, CognitoUserSession, CognitoRefreshToken } from 'amazon-cognito-identity-js';
import { CONFIG } from '../api/config';
import { 
  saveIdToken, 
  clearIdToken, 
  saveSessionData, 
  getSessionData,
  clearSessionData, 
  saveRefreshToken, 
  getRefreshToken, 
  clearRefreshToken 
} from './storage';

class MemoryStorage {
  private data: Record<string, string> = {};

  setItem(key: string, value: string): void {
    this.data[key] = value;
  }

  getItem(key: string): string | null {
    return this.data[key] || null;
  }

  removeItem(key: string): void {
    delete this.data[key];
  }

  clear(): void {
    this.data = {};
  }
}

const customStorage = new MemoryStorage();

const poolData = {
  UserPoolId: CONFIG.USER_POOL_ID,
  ClientId: CONFIG.CLIENT_ID,
  Storage: customStorage
};

const userPool = new CognitoUserPool(poolData);

export const signIn = (email: string, password: string): Promise<CognitoUserSession> => {
  return new Promise((resolve, reject) => {
    const authenticationData = { Username: email, Password: password };
    const authenticationDetails = new AuthenticationDetails(authenticationData);
    
    const userData = { Username: email, Pool: userPool };
    const cognitoUser = new CognitoUser(userData);
    
    cognitoUser.authenticateUser(authenticationDetails, {
      onSuccess: async (result) => {
        try {
          const idToken = result.getIdToken().getJwtToken();
          const refreshToken = result.getRefreshToken().getToken();
          await saveIdToken(idToken);
          await saveRefreshToken(refreshToken);
          await saveSessionData(JSON.stringify({
            email: cognitoUser.getUsername(),
            role: getEffectiveRole(result)
          }));
          resolve(result);
        } catch (storageErr) {
          reject(storageErr);
        }
      },
      onFailure: (err) => reject(err),
      newPasswordRequired: (userAttributes) => {
        resolve({
          challenge: 'NEW_PASSWORD_REQUIRED',
          userAttributes,
          cognitoUser
        } as any);
      }
    });
  });
};

export const forgotPassword = (email: string): Promise<void> => {
  return new Promise((resolve, reject) => {
    const userData = { Username: email, Pool: userPool };
    const cognitoUser = new CognitoUser(userData);
    cognitoUser.forgotPassword({
      onSuccess: () => resolve(),
      onFailure: (err) => reject(err),
    });
  });
};

export const confirmForgotPassword = (email: string, code: string, newPassword: string): Promise<void> => {
  return new Promise((resolve, reject) => {
    const userData = { Username: email, Pool: userPool };
    const cognitoUser = new CognitoUser(userData);
    cognitoUser.confirmPassword(code, newPassword, {
      onSuccess: () => resolve(),
      onFailure: (err) => reject(err),
    });
  });
};

export const signOut = async (): Promise<void> => {
  try {
    const cognitoUser = userPool.getCurrentUser();
    if (cognitoUser) {
      cognitoUser.signOut();
    }
  } catch (err) {
    console.warn('Cognito pool signOut failed', err);
  }
  
  try {
    await clearIdToken();
  } catch (err) {
    console.warn('Failed to clear ID token during signOut', err);
  }
  
  try {
    await clearRefreshToken();
  } catch (err) {
    console.warn('Failed to clear refresh token during signOut', err);
  }
  
  try {
    await clearSessionData();
  } catch (err) {
    console.warn('Failed to clear session data during signOut', err);
  }
};

export const refreshSession = async (): Promise<string | null> => {
  try {
    const refreshTokenStr = await getRefreshToken();
    const sessionDataStr = await getSessionData();
    
    if (!refreshTokenStr || !sessionDataStr) {
      return null;
    }
    
    const sessionData = JSON.parse(sessionDataStr);
    const email = sessionData.email;
    
    return new Promise((resolve) => {
      const userData = { Username: email, Pool: userPool };
      const cognitoUser = new CognitoUser(userData);
      const refreshToken = new CognitoRefreshToken({ RefreshToken: refreshTokenStr });
      
      cognitoUser.refreshSession(refreshToken, async (err, result) => {
        if (err) {
          console.warn('Failed to refresh Cognito session silently', err);
          resolve(null);
        } else {
          try {
            const newIdToken = result.getIdToken().getJwtToken();
            await saveIdToken(newIdToken);
            resolve(newIdToken);
          } catch (storageErr) {
            console.warn('Failed to save refreshed token in silent refresh', storageErr);
            resolve(null);
          }
        }
      });
    });
  } catch (e) {
    console.warn('Silent refresh encountered error', e);
    return null;
  }
};

export const getEffectiveRole = (session: CognitoUserSession | null): string => {
  if (!session) return 'unknown';
  const payload = session.getIdToken().payload;
  const groups = payload['cognito:groups'] || [];
  
  const groupArray = Array.isArray(groups) ? groups : [groups];
  const normalizedGroups = groupArray.map(g => String(g).toLowerCase());
  
  if (normalizedGroups.includes('owner')) return 'owner';
  if (normalizedGroups.includes('admin')) return 'owner'; 
  if (normalizedGroups.includes('staff')) return 'staff';
  if (normalizedGroups.includes('client')) return 'client';
  
  const email = (payload.email || '').toLowerCase().trim();
  if (['mattnicomn10@gmail.com', 'support@toganddogs.usmissionhero.com'].includes(email)) {
    return 'owner';
  }
  
  return 'unknown';
};
