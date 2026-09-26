// BannerAd — stub for Expo Go development
// Real AdMob loads automatically in the production native build
import { View } from 'react-native'

interface Props {
  size?: string
}

export function BannerAd({ size }: Props) {
  // Returns empty view in Expo Go — AdMob loads in native build
  return <View style={{ height: 0 }} />
}
