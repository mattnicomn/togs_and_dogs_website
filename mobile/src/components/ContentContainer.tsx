import React from 'react';
import { View, useWindowDimensions, StyleSheet } from 'react-native';

interface ContentContainerProps {
  children: React.ReactNode;
  maxWidth?: number;
  style?: any;
}

export const ContentContainer: React.FC<ContentContainerProps> = ({
  children,
  maxWidth = 600,
  style,
}) => {
  const { width } = useWindowDimensions();
  const isTablet = width >= 768;

  return (
    <View style={[styles.container, isTablet && { maxWidth, alignSelf: 'center', width: '100%' }, style]}>
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});
