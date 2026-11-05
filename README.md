# 🥚 Yumurta Depo Yönetim Sistemi

Ortak yumurta deposunu kullanan 3 kişi için stok takibi, tedarik/satış kaydı, firma ve kullanıcı yönetim paneli ile muhasebe raporlama uygulaması.

## Özellikler

- **Adet Bazlı Stok Takibi:** Başlangıç Stoğu + Toplam Alınan - Toplam Satılan = Net Stok (Adet)
- **Firma Seçimli Tedarik Girişi:** Kayıtlı tedarikçi firmalar arasından seçimle adet ve birim fiyat üzerinden alım kaydı
- **Firma Seçimli Satış Girişi:** Kayıtlı alıcı firmalar arasından seçimle satış kaydı (anlık stok kontrolü ile)
- **Kişisel Hesap:** 3 çalışanın her biri kendi alış ve satış geçmişini ayrı görür
- **Tarih Aralıklı Muhasebe Raporu:** İstenen iki tarih arası toplam alış, satış, net kâr/zarar ve çeşit bazında kâr tablosu (Yazdır / PDF desteği)
- **Yönetim Paneli (`/yonetim`):**
  - Tedarikçi firmaları ekleme, düzenleme, silme
  - Alıcı firmaları ekleme, düzenleme, silme
  - Yumurta cinslerini ekleme, düzenleme, silme ve **başlangıç stoğu** girme
  - Kullanıcı isimlerini ve şifrelerini değiştirme, yeni kullanıcı ekleme/silme

## Çalıştırma

```bash
cd Projeler/yumurta-depo
python3 app.py
```

Tarayıcıda: `http://localhost:5050` (veya yerel ağda `http://192.168.1.14:5050`)

## Varsayılan Kullanıcılar

| Kullanıcı | Şifre | İsim |
|---|---|---|
| ahmet | ahmet123 | Ahmet |
| mehmet | mehmet123 | Mehmet |
| ali | ali123 | Ali |

*(Şifreleri ve isimleri Yönetim panelinden istediğiniz zaman değiştirebilirsiniz)*
