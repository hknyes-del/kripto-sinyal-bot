"""
Optimal Trade Entry (OTE) hesaplama
Fibonacci 0.705 - 0.79 bantları
"""


def calculate_ote_zone(swing_low, swing_high, direction):
    """
    OTE bölgesini hesapla
    """
    range_size = swing_high - swing_low
    
    if direction == 'long':
        # Long için: Düşüşten sonra yukarı dönüş
        ote_705 = swing_high - (range_size * 0.705)
        ote_79 = swing_high - (range_size * 0.79)
        
        return {
            'zone_low': min(ote_705, ote_79),
            'zone_high': max(ote_705, ote_79),
            'optimal_entry': (ote_705 + ote_79) / 2,
            'band': '0.705 - 0.79'
        }
    
    else:  # direction == 'short'
        # Short için: Yükselişten sonra aşağı dönüş
        ote_705 = swing_low + (range_size * 0.705)
        ote_79 = swing_low + (range_size * 0.79)
        
        return {
            'zone_low': min(ote_705, ote_79),
            'zone_high': max(ote_705, ote_79),
            'optimal_entry': (ote_705 + ote_79) / 2,
            'band': '0.705 - 0.79'
        }