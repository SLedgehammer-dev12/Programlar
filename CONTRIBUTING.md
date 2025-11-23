# Katkıda Bulunma Rehberi

Bu projeye katkıda bulunmayı düşündüğünüz için teşekkür ederiz! Bu rehber, katkı sürecini kolaylaştırmak için hazırlanmıştır.

## Katkı Süreci

### 1. Repository'yi Fork Edin (Dış Katkıcılar İçin)
Eğer collaborator değilseniz, repository'yi fork edin:
1. GitHub'da repository sayfasının sağ üst köşesindeki "Fork" butonuna tıklayın
2. Kendi hesabınıza fork edin

### 2. Repository'yi Klonlayın
```bash
# Collaborator iseniz
git clone https://github.com/SLedgehammer-dev12/Programlar.git

# Fork ettiyseniz
git clone https://github.com/KULLANICI_ADINIZ/Programlar.git
```

### 3. Yeni Branch Oluşturun
```bash
git checkout -b ozellik/aciklayici-isim
```

Branch isimlendirme önerileri:
- `ozellik/yeni-program` - Yeni özellik eklerken
- `duzeltme/hata-aciklamasi` - Hata düzeltirken
- `dokuman/guncelleme` - Dokümantasyon güncellerken

### 4. Değişikliklerinizi Yapın
- Kod yazarken açık ve anlaşılır olun
- Gerektiğinde yorum satırları ekleyin
- Tutarlı bir kod stili kullanın

### 5. Değişiklikleri Commit Edin
```bash
git add .
git commit -m "Açıklayıcı commit mesajı"
```

**İyi Commit Mesajları:**
- ✅ "Kullanıcı girişi için doğrulama eklendi"
- ✅ "README'de kurulum adımları güncellendi"
- ❌ "düzeltme"
- ❌ "update"

### 6. Push Edin
```bash
git push origin ozellik/aciklayici-isim
```

### 7. Pull Request Oluşturun
1. GitHub'da repository sayfasına gidin
2. "Pull requests" sekmesine tıklayın
3. "New pull request" butonuna tıklayın
4. Branch'inizi seçin
5. Açıklayıcı bir başlık ve açıklama yazın:
   - Ne değiştirdiniz?
   - Neden bu değişikliği yaptınız?
   - Nasıl test ettiniz?

## Kod İncelemeleri

Pull request'iniz gözden geçirilecektir. Bu süreçte:
- Geri bildirim alabilirsiniz
- Değişiklik istekleri olabilir
- Sorular sorulabilir

Lütfen yapıcı geri bildirimlere açık olun ve gerekli değişiklikleri yapın.

## İletişim

### Issues (Sorunlar)
- Hata raporları için Issue açın
- Özellik önerileri için Issue açın
- Sorularınızı Issues'da sorun

### Pull Requests
- Her Pull Request tek bir konuya odaklanmalıdır
- Büyük değişiklikler için önce Issue açarak tartışın

## En İyi Uygulamalar

### Kod Kalitesi
- Temiz ve okunabilir kod yazın
- Gereksiz kod karmaşıklığından kaçının
- Değişken ve fonksiyon isimleri açıklayıcı olmalı

### Dokümantasyon
- Yeni özellikler için dokümantasyon ekleyin
- README'yi gerektiğinde güncelleyin
- Karmaşık kod bloklarına yorum ekleyin

### Test
- Değişikliklerinizi test edin
- Mevcut işlevselliği bozmadığınızdan emin olun

### Commit Geçmişi
- Küçük ve mantıklı commitler yapın
- Her commit tek bir değişikliği içermeli
- Açıklayıcı commit mesajları kullanın

## Senkronizasyon

### Upstream Repository ile Senkron Kalma
Fork kullanıyorsanız, ana repository ile senkron kalmak için:

```bash
# Upstream ekleyin (bir kez)
git remote add upstream https://github.com/SLedgehammer-dev12/Programlar.git

# Upstream'den güncellemeleri çekin
git fetch upstream

# Ana branch'inizi güncelleyin
git checkout main
git merge upstream/main

# Fork'unuza gönderin
git push origin main
```

## Yardım

Herhangi bir sorunuz varsa:
- Issue açın
- Mevcut katkıcılara sorun
- Dokümantasyonu kontrol edin

Katkılarınız için teşekkür ederiz! 🎉
