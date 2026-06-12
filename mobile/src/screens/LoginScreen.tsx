import React, { useState } from 'react';
import {
  StyleSheet,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../auth/useAuth';
import { forgotPassword, confirmForgotPassword } from '../auth/cognito';
import { COLORS } from '../theme/colors';

// Converts raw Cognito error codes/messages into user-friendly copy
const getFriendlyAuthError = (e: any): string => {
  const msg: string = (e?.message || e?.code || '').toLowerCase();
  if (
    msg.includes('notauthorized') ||
    msg.includes('incorrect username or password') ||
    msg.includes('incorrect email or password') ||
    msg.includes('user does not exist') ||
    msg.includes('usernot') ||
    msg.includes('notfound')
  ) {
    return 'Incorrect email or password. Please try again.';
  }
  if (msg.includes('user is not confirmed')) {
    return 'Your account is not yet confirmed. Please check your email for a verification link.';
  }
  if (msg.includes('password reset required') || msg.includes('resetrequired')) {
    return 'A password reset is required. Please use Forgot Password below.';
  }
  if (msg.includes('too many') || msg.includes('limitexceeded') || msg.includes('throttling')) {
    return 'Too many attempts. Please wait a moment and try again.';
  }
  if (msg.includes('network') || msg.includes('fetch')) {
    return 'Network error. Please check your connection and try again.';
  }
  // Default safe fallback — never expose raw internal errors
  return 'Incorrect email or password. Please try again.';
};

type ScreenMode = 'login' | 'forgotSendCode' | 'forgotResetPassword';

export const LoginScreen = () => {
  const { login } = useAuth();
  const [mode, setMode] = useState<ScreenMode>('login');

  // Login fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Forgot password fields
  const [fpEmail, setFpEmail] = useState('');
  const [fpCode, setFpCode] = useState('');
  const [fpNewPassword, setFpNewPassword] = useState('');
  const [fpConfirmPassword, setFpConfirmPassword] = useState('');
  const [fpSuccess, setFpSuccess] = useState<string | null>(null);

  const handleLogin = async () => {
    if (!email.trim() || !password) {
      setError('Please enter your email and password.');
      return;
    }
    setError(null);
    setIsLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
    } catch (e: any) {
      setError(getFriendlyAuthError(e));
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendResetCode = async () => {
    if (!fpEmail.trim()) {
      setError('Please enter your email address.');
      return;
    }
    setError(null);
    setIsLoading(true);
    try {
      await forgotPassword(fpEmail.trim().toLowerCase());
      setFpSuccess(null);
      setMode('forgotResetPassword');
    } catch (e: any) {
      // Never confirm whether email exists — generic message
      setError('If this email is registered, you will receive a reset code shortly.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirmReset = async () => {
    if (!fpCode.trim() || !fpNewPassword || !fpConfirmPassword) {
      setError('Please fill in all fields.');
      return;
    }
    if (fpNewPassword !== fpConfirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    if (fpNewPassword.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setError(null);
    setIsLoading(true);
    try {
      await confirmForgotPassword(fpEmail.trim().toLowerCase(), fpCode.trim(), fpNewPassword);
      setFpSuccess('Password reset successfully. You can now log in with your new password.');
      setFpCode('');
      setFpNewPassword('');
      setFpConfirmPassword('');
    } catch (e: any) {
      const msg = (e?.message || '').toLowerCase();
      if (msg.includes('codemismatch') || msg.includes('invalid verification code') || msg.includes('invalid code')) {
        setError('Invalid or expired reset code. Please request a new one.');
      } else if (msg.includes('expired')) {
        setError('This reset code has expired. Please request a new one.');
      } else {
        setError('Failed to reset password. Please check your code and try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const switchToForgotPassword = () => {
    setError(null);
    setFpSuccess(null);
    setFpEmail(email); // pre-fill with what user already typed
    setMode('forgotSendCode');
  };

  const switchToLogin = () => {
    setError(null);
    setFpSuccess(null);
    setMode('login');
  };

  // ── Forgot Password: Send Code ──────────────────────────────────────
  if (mode === 'forgotSendCode') {
    return (
      <SafeAreaView style={styles.safeArea}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.keyboardView}
        >
          <ScrollView contentContainerStyle={styles.scrollContent}>
            <View style={styles.headerContainer}>
              <Text style={styles.logoIcon}>🔑</Text>
              <Text style={styles.logoText}>Tog & Dogs</Text>
              <Text style={styles.subtitle}>Reset Password</Text>
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>Forgot Password</Text>
              <Text style={styles.cardHint}>
                Enter your email address and we'll send you a reset code.
              </Text>

              {error && (
                <View style={styles.errorContainer}>
                  <Text style={styles.errorText}>{error}</Text>
                </View>
              )}

              <View style={styles.inputGroup}>
                <Text style={styles.label}>Email Address</Text>
                <TextInput
                  style={styles.input}
                  value={fpEmail}
                  onChangeText={setFpEmail}
                  placeholder="email@example.com"
                  placeholderTextColor={COLORS.textMuted}
                  autoCapitalize="none"
                  keyboardType="email-address"
                  autoComplete="email"
                />
              </View>

              <TouchableOpacity
                style={styles.button}
                onPress={handleSendResetCode}
                disabled={isLoading}
              >
                {isLoading ? (
                  <ActivityIndicator color={COLORS.white} size="small" />
                ) : (
                  <Text style={styles.buttonText}>Send Reset Code</Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity style={styles.linkButton} onPress={switchToLogin}>
                <Text style={styles.linkText}>← Back to Sign In</Text>
              </TouchableOpacity>
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  // ── Forgot Password: Enter Code + New Password ────────────────────────
  if (mode === 'forgotResetPassword') {
    return (
      <SafeAreaView style={styles.safeArea}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.keyboardView}
        >
          <ScrollView contentContainerStyle={styles.scrollContent}>
            <View style={styles.headerContainer}>
              <Text style={styles.logoIcon}>🔑</Text>
              <Text style={styles.logoText}>Tog & Dogs</Text>
              <Text style={styles.subtitle}>Reset Password</Text>
            </View>

            <View style={styles.card}>
              <Text style={styles.cardTitle}>Enter Reset Code</Text>
              <Text style={styles.cardHint}>
                Check your email for a 6-digit code, then choose a new password.
              </Text>

              {error && (
                <View style={styles.errorContainer}>
                  <Text style={styles.errorText}>{error}</Text>
                </View>
              )}

              {fpSuccess && (
                <View style={styles.successContainer}>
                  <Text style={styles.successText}>{fpSuccess}</Text>
                  <TouchableOpacity style={[styles.button, { marginTop: 12 }]} onPress={switchToLogin}>
                    <Text style={styles.buttonText}>Back to Sign In</Text>
                  </TouchableOpacity>
                </View>
              )}

              {!fpSuccess && (
                <>
                  <View style={styles.inputGroup}>
                    <Text style={styles.label}>Reset Code</Text>
                    <TextInput
                      style={styles.input}
                      value={fpCode}
                      onChangeText={setFpCode}
                      placeholder="6-digit code"
                      placeholderTextColor={COLORS.textMuted}
                      autoCapitalize="none"
                      keyboardType="number-pad"
                    />
                  </View>

                  <View style={styles.inputGroup}>
                    <Text style={styles.label}>New Password</Text>
                    <TextInput
                      style={styles.input}
                      value={fpNewPassword}
                      onChangeText={setFpNewPassword}
                      placeholder="At least 8 characters"
                      placeholderTextColor={COLORS.textMuted}
                      secureTextEntry
                      autoCapitalize="none"
                    />
                  </View>

                  <View style={styles.inputGroup}>
                    <Text style={styles.label}>Confirm New Password</Text>
                    <TextInput
                      style={styles.input}
                      value={fpConfirmPassword}
                      onChangeText={setFpConfirmPassword}
                      placeholder="Repeat new password"
                      placeholderTextColor={COLORS.textMuted}
                      secureTextEntry
                      autoCapitalize="none"
                    />
                  </View>

                  <TouchableOpacity
                    style={styles.button}
                    onPress={handleConfirmReset}
                    disabled={isLoading}
                  >
                    {isLoading ? (
                      <ActivityIndicator color={COLORS.white} size="small" />
                    ) : (
                      <Text style={styles.buttonText}>Reset Password</Text>
                    )}
                  </TouchableOpacity>

                  <TouchableOpacity style={styles.linkButton} onPress={() => setMode('forgotSendCode')}>
                    <Text style={styles.linkText}>← Resend Code</Text>
                  </TouchableOpacity>

                  <TouchableOpacity style={styles.linkButton} onPress={switchToLogin}>
                    <Text style={styles.linkText}>← Back to Sign In</Text>
                  </TouchableOpacity>
                </>
              )}
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    );
  }

  // ── Login ─────────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.keyboardView}
      >
        <ScrollView contentContainerStyle={styles.scrollContent}>
          <View style={styles.headerContainer}>
            <Text style={styles.logoIcon}>🐾</Text>
            <Text style={styles.logoText}>Tog & Dogs</Text>
            <Text style={styles.subtitle}>Operations Portal</Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Sign In</Text>

            {error && (
              <View style={styles.errorContainer}>
                <Text style={styles.errorText}>{error}</Text>
              </View>
            )}

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Email Address</Text>
              <TextInput
                style={styles.input}
                value={email}
                onChangeText={setEmail}
                placeholder="email@example.com"
                placeholderTextColor={COLORS.textMuted}
                autoCapitalize="none"
                keyboardType="email-address"
                autoComplete="email"
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.label}>Password</Text>
              <TextInput
                style={styles.input}
                value={password}
                onChangeText={setPassword}
                placeholder="Enter password"
                placeholderTextColor={COLORS.textMuted}
                secureTextEntry
                autoCapitalize="none"
                autoComplete="password"
              />
            </View>

            <TouchableOpacity
              style={styles.button}
              onPress={handleLogin}
              disabled={isLoading}
            >
              {isLoading ? (
                <ActivityIndicator color={COLORS.white} size="small" />
              ) : (
                <Text style={styles.buttonText}>Log In</Text>
              )}
            </TouchableOpacity>

            <TouchableOpacity style={styles.linkButton} onPress={switchToForgotPassword}>
              <Text style={styles.linkText}>Forgot password?</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.footerContainer}>
            <Text style={styles.footerText}>Secure AWS Cognito Authentication</Text>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  keyboardView: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  headerContainer: {
    alignItems: 'center',
    marginBottom: 32,
  },
  logoIcon: {
    fontSize: 48,
    marginBottom: 8,
  },
  logoText: {
    fontSize: 28,
    fontWeight: '800',
    color: COLORS.primary,
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 16,
    color: COLORS.text,
    fontWeight: '600',
    opacity: 0.8,
  },
  card: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 16,
    padding: 24,
    shadowColor: COLORS.text,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 12,
    elevation: 4,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
  },
  cardTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.text,
    marginBottom: 20,
  },
  errorContainer: {
    backgroundColor: '#fff1f2',
    borderWidth: 1,
    borderColor: '#fecdd3',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  errorText: {
    color: COLORS.danger,
    fontSize: 14,
    fontWeight: '600',
  },
  successContainer: {
    backgroundColor: '#f0fdf4',
    borderWidth: 1,
    borderColor: '#bbf7d0',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  successText: {
    color: '#166534',
    fontSize: 14,
    fontWeight: '600',
  },
  cardHint: {
    fontSize: 14,
    color: COLORS.textMuted,
    marginBottom: 20,
    lineHeight: 20,
  },
  linkButton: {
    alignItems: 'center',
    marginTop: 16,
    paddingVertical: 4,
  },
  linkText: {
    color: COLORS.primary,
    fontSize: 14,
    fontWeight: '700',
  },
  inputGroup: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.text,
    marginBottom: 6,
  },
  input: {
    backgroundColor: COLORS.background,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 16,
    color: COLORS.text,
  },
  button: {
    backgroundColor: COLORS.primary,
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
    shadowColor: COLORS.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 3,
  },
  buttonText: {
    color: COLORS.white,
    fontSize: 16,
    fontWeight: '700',
  },
  footerContainer: {
    alignItems: 'center',
    marginTop: 32,
  },
  footerText: {
    fontSize: 12,
    color: COLORS.textMuted,
    fontWeight: '600',
  },
});
