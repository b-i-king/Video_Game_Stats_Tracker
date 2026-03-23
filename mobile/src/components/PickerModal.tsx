import {
  Modal, View, Text, TouchableOpacity, FlatList,
  TouchableWithoutFeedback, StyleSheet,
} from 'react-native';

const GOLD = '#C4A035';
const CARD = '#1C1C1C';
const BORDER = '#2A2A2A';
const BG = '#111111';

interface Props {
  visible: boolean;
  title: string;
  options: string[];
  selected?: string;
  onSelect: (value: string) => void;
  onClose: () => void;
}

export function PickerModal({ visible, title, options, selected, onSelect, onClose }: Props) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableWithoutFeedback onPress={onClose}>
        <View style={styles.overlay} />
      </TouchableWithoutFeedback>

      <View style={styles.sheet}>
        <View style={styles.handle} />
        <Text style={styles.title}>{title}</Text>

        <FlatList
          data={options}
          keyExtractor={(item) => item}
          style={{ maxHeight: 380 }}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[styles.item, item === selected && styles.itemSelected]}
              onPress={() => { onSelect(item); onClose(); }}
            >
              <Text style={[styles.itemText, item === selected && styles.itemTextSelected]}>
                {item || 'N/A'}
              </Text>
              {item === selected && <Text style={styles.check}>✓</Text>}
            </TouchableOpacity>
          )}
        />

        <TouchableOpacity style={styles.cancelBtn} onPress={onClose}>
          <Text style={styles.cancelText}>Cancel</Text>
        </TouchableOpacity>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)' },
  sheet: {
    backgroundColor: CARD,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingTop: 12,
    paddingBottom: 36,
  },
  handle: {
    width: 40, height: 4, backgroundColor: '#444',
    borderRadius: 2, alignSelf: 'center', marginBottom: 14,
  },
  title: {
    color: GOLD, fontSize: 15, fontWeight: '700',
    textAlign: 'center', marginBottom: 8, paddingHorizontal: 20,
  },
  item: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingVertical: 14, paddingHorizontal: 20,
    borderBottomWidth: 1, borderBottomColor: BORDER,
  },
  itemSelected: { backgroundColor: 'rgba(196,160,53,0.12)' },
  itemText: { color: '#CCC', fontSize: 15 },
  itemTextSelected: { color: GOLD, fontWeight: '700' },
  check: { color: GOLD, fontSize: 16 },
  cancelBtn: {
    marginTop: 10, marginHorizontal: 20, paddingVertical: 14,
    backgroundColor: BG, borderRadius: 10, alignItems: 'center',
  },
  cancelText: { color: '#888', fontSize: 15, fontWeight: '600' },
});
