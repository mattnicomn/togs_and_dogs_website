/**
 * Phase 24A-3: Test Runner Sanity
 *
 * Proves Jest starts, TSX transforms, React Native renders,
 * and Testing Library queries work.
 */
import React from 'react';
import { Text, View } from 'react-native';
import { render, screen } from '@testing-library/react-native';

describe('Test Runner Sanity', () => {
  it('renders a React Native component', () => {
    render(
      <View>
        <Text>Hello Test</Text>
      </View>
    );
    expect(screen.getByText('Hello Test')).toBeTruthy();
  });

  it('supports TypeScript types', () => {
    const value: number = 42;
    expect(value).toBe(42);
  });
});
