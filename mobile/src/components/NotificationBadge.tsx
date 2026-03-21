import { View, Text, StyleSheet } from 'react-native';

const GOLD = '#C4A035';

interface NotificationBadgeProps {
  count: number;
  /** Max number to display before showing "99+" style cap */
  cap?: number;
}

/**
 * Small circular badge used on tab icons or anywhere a numeric count is needed.
 * Returns null when count is 0 so the caller doesn't need to conditionally render.
 */
export function NotificationBadge({ count, cap = 99 }: NotificationBadgeProps) {
  if (count <= 0) return null;

  const label = count > cap ? `${cap}+` : String(count);

  return (
    <View style={styles.badge}>
      <Text style={styles.text}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    backgroundColor: GOLD,
    borderRadius: 10,
    minWidth: 20,
    height: 20,
    paddingHorizontal: 5,
    justifyContent: 'center',
    alignItems: 'center',
  },
  text: {
    color: '#000',
    fontSize: 11,
    fontWeight: '700',
  },
});
