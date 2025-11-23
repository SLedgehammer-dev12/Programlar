# Çoklu Bilgisayarlarda Çalışma Rehberi

Bu rehber, aynı repository üzerinde farklı bilgisayarlardan çalışmak için gerekli adımları açıklar.

## İlk Kurulum

### Her Bilgisayarda Yapılması Gerekenler

#### 1. Git Kurulumu
Eğer yüklü değilse, Git'i yükleyin:
- **Windows**: [git-scm.com](https://git-scm.com/download/win) adresinden indirin
- **Mac**: `brew install git` veya [git-scm.com](https://git-scm.com/download/mac)
- **Linux**: `sudo apt-get install git` veya `sudo yum install git`

#### 2. Git Yapılandırması
Her bilgisayarda kullanıcı bilgilerinizi ayarlayın:

```bash
git config --global user.name "Adınız Soyadınız"
git config --global user.email "email@example.com"
```

**Önemli**: Email adresiniz GitHub hesabınızdakiyle aynı olmalıdır.

#### 3. SSH Key Oluşturma (Önerilen)
SSH kullanarak daha güvenli bağlantı sağlayabilirsiniz:

```bash
# SSH key oluşturun
ssh-keygen -t ed25519 -C "email@example.com"

# SSH key'i kopyalayın
# Linux/Mac:
cat ~/.ssh/id_ed25519.pub

# Windows (Git Bash):
clip < ~/.ssh/id_ed25519.pub
```

GitHub'da SSH key'i ekleyin:
1. GitHub > Settings > SSH and GPG keys
2. "New SSH key" butonuna tıklayın
3. Kopyaladığınız key'i yapıştırın
4. "Add SSH key" ile kaydedin

#### 4. Repository'yi Klonlama

HTTPS ile:
```bash
git clone https://github.com/SLedgehammer-dev12/Programlar.git
cd Programlar
```

SSH ile (önerilen):
```bash
git clone git@github.com:SLedgehammer-dev12/Programlar.git
cd Programlar
```

## Günlük Çalışma Akışı

### Çalışmaya Başlarken (Her Oturumda)

1. **En son değişiklikleri çekin:**
   ```bash
   cd Programlar
   git pull origin main
   ```

2. **Durumu kontrol edin:**
   ```bash
   git status
   ```

### Değişiklik Yaparken

1. **Dosyalarınızı düzenleyin**

2. **Değişiklikleri kontrol edin:**
   ```bash
   git status
   git diff
   ```

3. **Değişiklikleri stage'e alın:**
   ```bash
   # Tüm değişiklikleri eklemek için
   git add .
   
   # Belirli dosyaları eklemek için
   git add dosya1.txt dosya2.txt
   ```

4. **Commit yapın:**
   ```bash
   git commit -m "Açıklayıcı mesaj: Ne değiştirdim"
   ```

5. **GitHub'a gönderin:**
   ```bash
   git push origin main
   ```

### Çalışmayı Bitirirken

1. **Tüm değişikliklerin commit edildiğinden emin olun:**
   ```bash
   git status
   ```

2. **Son kez push yapın:**
   ```bash
   git push origin main
   ```

## Olası Problemler ve Çözümleri

### 1. Push Reddedildi (Remote changes)

**Hata:**
```
! [rejected]        main -> main (fetch first)
error: failed to push some refs
```

**Çözüm:**
```bash
# Önce remote değişiklikleri çekin
git pull origin main

# Eğer merge conflict yoksa, push yapın
git push origin main
```

### 2. Merge Conflict (Çakışma)

**Ne zaman olur:** İki bilgisayarda aynı dosyanın aynı satırları değiştirilmişse.

**Çözüm:**
```bash
# Conflictleri görmek için
git status

# Her conflict dosyasını açın ve düzenleyin
# <<<<<<< HEAD ve >>>>>>> işaretleri arasındaki kısmı düzeltin

# Düzeltmeden sonra
git add dosya-adi
git commit -m "Merge conflict çözüldü"
git push origin main
```

### 3. Yanlışlıkla Yanlış Değişiklik Yapıldı

**Henüz commit yapılmadıysa:**
```bash
# Belirli bir dosyayı geri al
git checkout -- dosya-adi

# Tüm değişiklikleri geri al
git reset --hard HEAD
```

**Commit yapıldıysa ama push yapılmadıysa:**
```bash
# Son commit'i geri al (değişiklikleri koru)
git reset --soft HEAD~1

# Son commit'i tamamen sil
git reset --hard HEAD~1
```

### 4. Farklı Branch'lerde Çalışma

**Yeni branch oluşturma:**
```bash
git checkout -b yeni-branch-adi
```

**Branch'ler arası geçiş:**
```bash
# Mevcut branch'leri görmek
git branch -a

# Branch'e geçiş
git checkout branch-adi
```

## En İyi Uygulamalar

### ✅ Yapılması Gerekenler

1. **Her oturum başında pull yapın:**
   ```bash
   git pull origin main
   ```

2. **Sık sık commit yapın:**
   - Küçük, anlamlı parçalarda commit yapın
   - Her commit tek bir mantıksal değişiklik içermeli

3. **Açıklayıcı commit mesajları yazın:**
   - ✅ "Kullanıcı arayüzü bileşeni eklendi"
   - ❌ "update"

4. **Push yapmadan önce test edin:**
   - Kodunuzun çalıştığından emin olun
   - Hataları kontrol edin

5. **Branch kullanın:**
   - Büyük değişiklikler için ayrı branch oluşturun
   - Main branch'i stabil tutun

### ❌ Yapılmaması Gerekenler

1. **Pull yapmadan çalışmaya başlamayın**
2. **Yarım kalmış işleri push etmeyin**
3. **Binary dosyalar eklemekten kaçının** (büyük resimler, videolar, vb.)
4. **Hassas bilgileri commit etmeyin** (şifreler, API anahtarları)
5. **Force push yapmayın** (`git push --force`) başkaları da çalışıyorsa

## Hızlı Komut Referansı

```bash
# Durum kontrolü
git status

# Değişiklikleri görmek
git diff

# Son değişiklikleri çekmek
git pull origin main

# Değişiklikleri eklemek
git add .

# Commit yapmak
git commit -m "Mesaj"

# Push yapmak
git push origin main

# Geçmişi görmek
git log --oneline -10

# Branch listesi
git branch -a

# Yeni branch
git checkout -b branch-adi

# Branch değiştir
git checkout branch-adi
```

## Otomatik Senkronizasyon

### Git Hooks ile Otomatik Pull

`.git/hooks/post-checkout` dosyası oluşturun:
```bash
#!/bin/bash
git pull origin main
```

Executable yapın:
```bash
chmod +x .git/hooks/post-checkout
```

## Yedekleme Stratejisi

1. **GitHub'daki kod zaten bir yedektir**
2. **Critical dosyalar için ekstra backup:**
   - Cloud storage (Google Drive, Dropbox)
   - External disk
   - Farklı bir git remote

## Sorun Giderme

### Yardım Almak

1. **Git durumunu kontrol edin:**
   ```bash
   git status
   git log --oneline -5
   ```

2. **Hata mesajını okuyun ve anlayın**

3. **GitHub Issues'da sorun:**
   - Repository'nin Issues bölümünde yeni issue açın
   - Hata mesajını ve yaptıklarınızı açıklayın

4. **Git dokümantasyonu:**
   ```bash
   git help <komut>
   # Örnek: git help pull
   ```

## Gelişmiş Konular

### Stash Kullanımı
Yarım kalmış işleri geçici olarak kaydetmek için:

```bash
# Değişiklikleri sakla
git stash

# Saklananları görmek
git stash list

# Geri yüklemek
git stash pop
```

### Remote Repository Kontrolü

```bash
# Remote'ları görmek
git remote -v

# Remote URL'i değiştirmek
git remote set-url origin <yeni-url>
```

### Tag Kullanımı (Sürüm İşaretleme)

```bash
# Tag oluştur
git tag -a v1.0 -m "İlk sürüm"

# Tag'leri gönder
git push origin --tags
```

## Özet

En önemli kurallar:
1. 📥 **Çalışmaya başlamadan önce**: `git pull`
2. 💾 **Sık sık**: `git commit`
3. 📤 **Bitirirken**: `git push`
4. 🔍 **Her zaman**: `git status`

Bu kurallara uyarak birden fazla bilgisayarda sorunsuz çalışabilirsiniz!
