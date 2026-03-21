import { View, StyleSheet, ActivityIndicator, Text } from 'react-native';
import { WebView } from 'react-native-webview';
import { useState } from 'react';

const GOLD = '#C4A035';
const BG = '#111111';
const BORDER = '#2A2A2A';

interface InteractiveChartProps {
  /** Public GCS URL of the Plotly HTML file */
  url: string;
  height?: number;
}

/**
 * Wraps the GCS-hosted Plotly interactive chart in a WebView.
 * The URL follows the convention set in gcs_utils.py:
 *   twitter/interactive/{player_slug}_{game_slug}.html
 */
export function InteractiveChart({ url, height = 280 }: InteractiveChartProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  return (
    <View style={[styles.container, { height }]}>
      {loading && !error && (
        <View style={styles.overlay}>
          <ActivityIndicator color={GOLD} />
        </View>
      )}
      {error ? (
        <View style={styles.overlay}>
          <Text style={styles.errorText}>Chart unavailable</Text>
          <Text style={styles.errorSub}>Submit stats to generate a chart</Text>
        </View>
      ) : (
        <WebView
          source={{ uri: url }}
          style={styles.webview}
          onLoadEnd={() => setLoading(false)}
          onError={() => { setLoading(false); setError(true); }}
          scrollEnabled={false}
          showsHorizontalScrollIndicator={false}
          showsVerticalScrollIndicator={false}
          // Prevent the WebView from navigating away if the user taps a Plotly link
          onShouldStartLoadWithRequest={(req) => req.url === url}
        />
      )}
    </View>
  );
}

function chartUrl(playerName: string, gameName: string, gameInstallment?: string): string {
  const playerSlug = playerName.toLowerCase().replace(/\s+/g, '_');
  const gameSlug = gameName.toLowerCase().replace(/\s+/g, '_');
  const installSlug = gameInstallment ? `_${gameInstallment.toLowerCase().replace(/\s+/g, '_')}` : '';
  return `https://storage.googleapis.com/game-tracker-charts/twitter/interactive/${playerSlug}_${gameSlug}${installSlug}.html`;
}

/** Convenience helper — builds the GCS URL from player/game names */
InteractiveChart.urlFor = chartUrl;

const styles = StyleSheet.create({
  container: {
    borderRadius: 10,
    borderWidth: 1,
    borderColor: BORDER,
    overflow: 'hidden',
    backgroundColor: BG,
  },
  webview: { flex: 1, backgroundColor: BG },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: BG,
  },
  errorText: { color: '#888', fontSize: 14, fontWeight: '600', marginBottom: 4 },
  errorSub: { color: '#555', fontSize: 12 },
});
