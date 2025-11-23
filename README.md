# Programlar
İş için kullanılan programlar

## Hakkında
Bu repository, iş için kullanılan programları ve araçları içerir. Farklı bilgisayarlardan çalışabilir ve belirlenen kişilerle paylaşılabilir.

## Başlangıç

> 📖 **Hızlı başlangıç için**: [QUICKSTART.md](QUICKSTART.md) dosyasına bakın  
> 📖 **Detaylı çoklu bilgisayar çalışma rehberi için**: [COLLABORATION.md](COLLABORATION.md) dosyasına bakın

### Gereksinimler
- Git yüklü olmalıdır
- GitHub hesabı

### Repository'yi Klonlama
Repository'yi bilgisayarınıza klonlamak için:

```bash
git clone https://github.com/SLedgehammer-dev12/Programlar.git
cd Programlar
```

### Farklı Bilgisayarlarda Çalışma

#### İlk Kurulum
1. Repository'yi her bilgisayara klonlayın:
   ```bash
   git clone https://github.com/SLedgehammer-dev12/Programlar.git
   ```

2. Git kullanıcı bilgilerinizi ayarlayın:
   ```bash
   git config user.name "Adınız"
   git config user.email "email@example.com"
   ```

#### Değişiklikleri Senkronize Etme

**Çalışmaya başlamadan önce:**
```bash
git pull origin main
```

**Değişikliklerinizi kaydetme:**
```bash
git add .
git commit -m "Açıklayıcı mesaj"
git push origin main
```

**Güncel kalmak için:**
Her çalışma oturumundan önce `git pull` komutunu çalıştırın.

## İşbirliği

### Repository Paylaşımı
Bu repository'yi başkalarıyla paylaşmak için:

1. **GitHub'da Settings > Collaborators** bölümüne gidin
2. "Add people" butonuna tıklayın
3. Eklemek istediğiniz kişinin GitHub kullanıcı adını veya email adresini girin
4. Uygun erişim seviyesini seçin:
   - **Read**: Sadece görüntüleme
   - **Write**: Değişiklik yapabilme
   - **Admin**: Tam yetki

### Katkıda Bulunma
Katkıda bulunmak isteyenler için lütfen [CONTRIBUTING.md](CONTRIBUTING.md) dosyasına bakın.

## Çalışma Akışı

### Branch (Dal) Kullanımı
Yeni özellikler için yeni branch oluşturun:

```bash
# Yeni branch oluştur ve geç
git checkout -b yeni-ozellik

# Değişikliklerinizi yapın ve commit edin
git add .
git commit -m "Yeni özellik eklendi"

# Branch'i GitHub'a gönderin
git push origin yeni-ozellik
```

### Pull Request Oluşturma
1. GitHub'da repository'nizi açın
2. "Pull requests" sekmesine gidin
3. "New pull request" butonuna tıklayın
4. Branch'inizi seçin ve açıklama ekleyin
5. "Create pull request" ile oluşturun

## Yardım ve Destek
Sorularınız için [Issues](https://github.com/SLedgehammer-dev12/Programlar/issues) bölümünü kullanabilirsiniz.

## Lisans
Bu proje ile ilgili lisans bilgileri için [LICENSE](LICENSE) dosyasına bakın.
