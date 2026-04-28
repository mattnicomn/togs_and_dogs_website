import { CognitoUserPool, CognitoUser, AuthenticationDetails } from 'amazon-cognito-identity-js';
import CONFIG from './config';

const poolData = {
  UserPoolId: CONFIG.USER_POOL_ID,
  ClientId: CONFIG.CLIENT_ID
};

const userPool = new CognitoUserPool(poolData);

export const signIn = (email, password) => {
  return new Promise((resolve, reject) => {
    const authenticationData = { Username: email, Password: password };
    const authenticationDetails = new AuthenticationDetails(authenticationData);
    
    const userData = { Username: email, Pool: userPool };
    const cognitoUser = new CognitoUser(userData);
    
    cognitoUser.authenticateUser(authenticationDetails, {
      onSuccess: (result) => resolve(result),
      onFailure: (err) => reject(err),
      newPasswordRequired: (userAttributes) => {
        // For this flow, we assume passwords are set to permanent via CLI first
        reject(new Error("New password required - handle in UI or set permanent via CLI"));
      }
    });
  });
};

export const signOut = () => {
  const cognitoUser = userPool.getCurrentUser();
  if (cognitoUser) {
    cognitoUser.signOut();
  }
};

export const getSession = () => {
  return new Promise((resolve, reject) => {
    const cognitoUser = userPool.getCurrentUser();
    if (!cognitoUser) return resolve(null);
    
    cognitoUser.getSession((err, session) => {
      if (err) return reject(err);
      if (!session.isValid()) return resolve(null);
      resolve(session);
    });
  });
};

export const getIdToken = async () => {
  const session = await getSession();
  return session ? session.getIdToken().getJwtToken() : null;
};

export const getEffectiveRole = (session) => {
  if (!session) return 'unknown';
  const payload = session.getIdToken().payload;
  const groups = payload['cognito:groups'] || [];
  
  // Handle case where groups might be a string (rare)
  const groupArray = Array.isArray(groups) ? groups : [groups];
  const normalizedGroups = groupArray.map(g => String(g).toLowerCase());
  
  if (normalizedGroups.includes('owner')) return 'owner';
  if (normalizedGroups.includes('admin')) return 'admin';
  if (normalizedGroups.includes('staff')) return 'staff';
  if (normalizedGroups.includes('client')) return 'client';
  
  const email = (payload.email || '').toLowerCase().trim();
  if (['mattnicomn10@gmail.com', 'support@toganddogs.usmissionhero.com'].includes(email)) {
    return 'owner';
  }
  
  return 'unknown';
};

