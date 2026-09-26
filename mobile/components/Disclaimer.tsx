import { View, Text, StyleSheet } from 'react-native'
import { Colors, FontSize } from '@/constants/theme'

export function Disclaimer() {
  return (
    <View style={styles.bar}>
      <Text style={styles.text}>
        ⚠️ Not SEBI registered. For educational purposes only. Not investment advice.
      </Text>
    </View>
  )
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: 'rgba(201,163,78,0.07)',
    borderTopWidth: 1,
    borderTopColor: 'rgba(201,163,78,0.15)',
    paddingVertical: 5,
    paddingHorizontal: 12,
    alignItems: 'center',
  },
  text: {
    color: 'rgba(201,163,78,0.6)',
    fontSize: FontSize.xs,
    fontFamily: 'Inter_400Regular',
    textAlign: 'center',
  },
})
