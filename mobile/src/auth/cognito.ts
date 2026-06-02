import { CognitoUserPool, CognitoUser, AuthenticationDetails, CognitoUserSession } from 'amazon-cognito-identity-js';
import { CONFIG } from '../api/config';
import { saveIdToken, clearIdToken, saveSessionData, clearSessionData } from './storage';

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
        const idToken = result.getIdToken().getJwtToken();
        await saveIdToken(idToken);
        await saveSessionData(JSON.stringify({
          email: cognitoUser.getUsername(),
          role: getEffectiveRole(result)
        }));
        resolve(result);
      },
      onFailure: (err) => reject(err),
      newPasswordRequired: (userAttributes) => {
        // Resolve custom challenge type mirroring web
        resolve({
          challenge: 'NEW_PASSWORD_REQUIRED',
          userAttributes,
          cognitoUser
        } as any);
      }
    });
  });
};

export const signOut = async (): Promise<void> => {
  const cognitoUser = userPool.getCurrentUser();
  if (cognitoUser) {
    cognitoUser.signOut();
  }
  await clearIdToken();
  await clearSessionData();
};

export const getEffectiveRole = (session: CognitoUserSession | null): string => {
  if (!session) return 'unknown';
  const payload = session.getIdToken().payload;
  const groups = payload['cognito:groups'] || [];
  
  const groupArray = Array.isArray(groups) ? groups : [groups];
  const normalizedGroups = groupArray.map(g => String(g).toLowerCase());
  
  if (normalizedGroups.includes('owner')) return 'owner';
  if (normalizedGroups.includes('admin')) return 'owner'; // map admin to owner dashboard/client layout
  if (normalizedGroups.includes('staff')) return 'staff';
  if (normalizedGroups.includes('client')) return 'client';
  
  const email = (payload.email || '').toLowerCase().trim();
  if (['mattnicomn10@gmail.com', 'support@toganddogs.usmissionhero.com'].includes(email)) {
    return 'owner';
  }
  
  return 'unknown';
};
