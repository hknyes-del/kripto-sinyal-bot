import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

class SinyalVeritabani:
    """Sinyalleri kaydet, TP/SL takibi yap"""
    
    def __init__(self, dosya_adi="sinyaller.json"):
        self.dosya_adi = dosya_adi
        self.sinyaller = self._yukle()
    
    def _yukle(self) -> List[Dict]:
        if os.path.exists(self.dosya_adi):
            with open(self.dosya_adi, 'r') as f:
                return json.load(f)
        return []
    
    def _kaydet(self):
        with open(self.dosya_adi, 'w') as f:
            json.dump(self.sinyaller, f, indent=2, default=str)
    
    def sinyal_ekle(self, sinyal: Dict):
        """Yeni sinyali kaydet"""
        sinyal['id'] = len(self.sinyaller) + 1
        sinyal['tarih'] = datetime.now().isoformat()
        sinyal['durum'] = 'Aktif'  # Aktif, TP1, TP2, TP3, SL, İptal
        sinyal['tp_seviye'] = 0
        sinyal['kar_yuzde'] = 0
        sinyal['notlar'] = ""
        
        self.sinyaller.append(sinyal)
        self._kaydet()
        return sinyal['id']
    
    def sinyal_guncelle(self, sinyal_id: int, durum: str, fiyat: float = None):
        """TP veya SL olduğunda güncelle"""
        for sinyal in self.sinyaller:
            if sinyal['id'] == sinyal_id:
                sinyal['durum'] = durum
                sinyal['kapanis_tarih'] = datetime.now().isoformat()
                if fiyat:
                    sinyal['kapanis_fiyat'] = fiyat
                    # Kar/Zarar hesapla
                    if sinyal['yon'] == 'BULLISH':
                        kar = (fiyat - sinyal['entry_fiyat']) / sinyal['entry_fiyat'] * 100
                    else:
                        kar = (sinyal['entry_fiyat'] - fiyat) / sinyal['entry_fiyat'] * 100
                    sinyal['kar_yuzde'] = round(kar, 2)
                    
                    # TP seviyesini belirle
                    if 'TP1' in durum:
                        sinyal['tp_seviye'] = 1
                    elif 'TP2' in durum:
                        sinyal['tp_seviye'] = 2
                    elif 'TP3' in durum:
                        sinyal['tp_seviye'] = 3
                
                self._kaydet()
                return True
        return False
    
    def istatistik(self) -> Dict:
        """Performans istatistikleri"""
        toplam = len(self.sinyaller)
        if toplam == 0:
            return {}
        
        aktif = len([s for s in self.sinyaller if s['durum'] == 'Aktif'])
        tp1 = len([s for s in self.sinyaller if s['tp_seviye'] >= 1])
        tp2 = len([s for s in self.sinyaller if s['tp_seviye'] >= 2])
        tp3 = len([s for s in self.sinyaller if s['tp_seviye'] >= 3])
        sl = len([s for s in self.sinyaller if s['durum'] == 'SL'])
        iptal = len([s for s in self.sinyaller if s['durum'] == 'İptal'])
        
        # Başarı oranı (TP1'e ulaşanlar)
        basari_orani = round(tp1 / (tp1 + sl) * 100, 2) if (tp1 + sl) > 0 else 0
        
        # Ortalama kar
        karlar = [s['kar_yuzde'] for s in self.sinyaller if s['durum'] != 'Aktif' and s['durum'] != 'İptal']
        ortalama_kar = round(sum(karlar) / len(karlar), 2) if karlar else 0
        
        return {
            'toplam': toplam,
            'aktif': aktif,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'sl': sl,
            'iptal': iptal,
            'basari_orani': basari_orani,
            'ortalama_kar': ortalama_kar
        }
    
    def gunluk_rapor(self) -> str:
        """Günlük performans raporu"""
        stats = self.istatistik()
        if not stats:
            return "Henüz sinyal yok."
        
        bugun = datetime.now().date()
        bugun_sinyaller = [s for s in self.sinyaller 
                          if datetime.fromisoformat(s['tarih']).date() == bugun]
        
        rapor = f"""
📊 *GÜNLÜK PERFORMANS RAPORU*
{bugun.strftime('%d.%m.%Y')}

📈 *BUGÜN*
• Toplam Sinyal: {len(bugun_sinyaller)}
• TP1: {len([s for s in bugun_sinyaller if s['tp_seviye'] >= 1])}
• TP2: {len([s for s in bugun_sinyaller if s['tp_seviye'] >= 2])}
• TP3: {len([s for s in bugun_sinyaller if s['tp_seviye'] >= 3])}
• SL: {len([s for s in bugun_sinyaller if s['durum'] == 'SL'])}

📊 *GENEL İSTATİSTİK*
• Toplam Sinyal: {stats['toplam']}
• Başarı Oranı: %{stats['basari_orani']}
• Ortalama Kar: %{stats['ortalama_kar']}
• TP1: {stats['tp1']} | TP2: {stats['tp2']} | TP3: {stats['tp3']}
• SL: {stats['sl']}

🏆 *EN İYİ SİNYAL*
"""
        return rapor

# Global veritabanı
sinyal_db = SinyalVeritabani()