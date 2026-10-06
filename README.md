# mCV

Flask ile geliştirilmiş, yönetim panelli kişisel özgeçmiş, portfolyo ve blog uygulaması.

![mCV ekran görüntüsü](https://github.com/user-attachments/assets/e8ef9cf5-8b14-4685-87c9-e351c744f0f5)

## Özellikler

- Özgeçmiş, yetenek, proje ve iletişim bölümleri
- Markdown tabanlı blog, arama ve etiket filtreleme
- İçerik ve görsel yönetim paneli
- Yönetici parolasıyla korunan tam ZIP yedekleme ve geri yükleme
- CSRF koruması ve doğrulanan görsel yükleme
- Docker healthcheck ve kalıcı veri volume'u
- Masaüstü ve mobil uyumlu arayüz

## Yapılandırma

Uygulamanın yalnızca üç zorunlu ortam değişkeni vardır:

```dotenv
SECRET_KEY=uretme-komutunun-ciktisini-buraya-yapistirin
ADMIN_USERNAME=yonetici
ADMIN_PASSWORD=benzersiz-ve-guclu-bir-parola
```

Üretim gereksinimleri:

- `SECRET_KEY` en az 32 karakter olmalıdır.
- `ADMIN_PASSWORD` en az 20 karakter olmalıdır.
- `ADMIN_USERNAME` başında veya sonunda boşluk içermemelidir.

`SECRET_KEY` üretmek için:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Eksik, boş veya gereksinimleri karşılamayan bir değerle uygulama başlamaz. `.env` dosyası Git ve Docker build context dışında tutulur; repodaki `.env.example` yalnız güvenli yer tutucular içerir.

## Yerel Geliştirme

Python 3.12 veya daha yeni bir sürüm kullanın.

### Linux ve macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
chmod 600 .env
```

`.env` içindeki üç değeri doldurduktan sonra:

```bash
set -a
source .env
set +a
python run.py
```

### Windows PowerShell

```powershell
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

`.env` içindeki üç değeri doldurduktan sonra değişkenleri mevcut PowerShell oturumuna yükleyip uygulamayı başlatın:

```powershell
Get-Content .env | ForEach-Object {
  if ($_ -match '^(?!#)\s*([^=]+)=(.*)$') {
    [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
  }
}
& .\.venv\Scripts\python.exe run.py
```

Uygulama `python-dotenv` kullanmaz; `.env` değerleri uygulama başlamadan önce kabuk ortamına yüklenmelidir.

Site `http://127.0.0.1:5000`, yönetim girişi `http://127.0.0.1:5000/admin/giris` adresindedir. `run.py` yalnız geliştirme için debug modunu açar ve güvenli cookie zorunluluğunu yerel HTTP için kapatır.

## Docker Doğrulaması

`compose.yaml`, yerel image ve volume doğrulaması içindir:

Henüz oluşturmadıysanız `.env.example` dosyasını `.env` olarak kopyalayın ve üç değeri doldurun. Linux/macOS üzerinde `chmod 600 .env` ile dosya erişimini sınırlandırın.

```bash
docker compose up -d --build
docker compose ps
curl --fail http://127.0.0.1:8000/healthz
docker compose logs -f app
```

Container portu yalnız `127.0.0.1:8000` üzerinde yayınlanır. Üretim cookie'si `Secure` olduğu için yönetim paneli üretimde HTTPS reverse proxy üzerinden kullanılmalıdır.

Container'ı durdurmak veriyi silmez:

```bash
docker compose down
```

`docker compose down -v` kalıcı `storage` volume'unu ve tüm yönetilen içeriği siler; normal kullanımda çalıştırılmamalıdır.

## Kalıcı Veri

İlk açılışta `seed/site.json`, `seed/blog`, `seed/uploads` ve `seed/branding` içeriği `storage/` yapısına kopyalanır. `storage/.initialized` işaretinden sonraki açılışlar mevcut veriyi değiştirmez. Bu nedenle sonraki deployment'larda `seed/` değişiklikleri üretim verisine otomatik birleştirilmez.

```text
storage/
├── state/       Site ayarları
├── blog/        Markdown yazıları
├── uploads/     Proje ve blog görselleri
└── branding/    Profil görseli ve favicon
```

Yerel Compose ve Dokploy üretim kurulumu kalıcı veriyi `/app/storage` yolundaki named volume'da tutar. Dosya tabanlı veri modeli nedeniyle uygulama tek worker, tek thread, tek replica ve `stop-first` deployment ile çalışır.

## Yedekleme ve Geri Yükleme

Yönetim panelindeki `/admin/yedekleme` sayfası taşınabilir bir mCV ZIP yedeği oluşturur. Arşiv şunları içerir:

- Site ayarları
- Blog yazıları
- Yüklenen proje ve blog görselleri
- Profil görseli ve favicon
- Dosya boyutlarıyla SHA-256 sağlama toplamlarını içeren sürümlü manifest

Geri yükleme arşiv yollarını, dosya türlerini, dosya sayısını, açılmış toplam boyutu ve sağlama toplamlarını doğrular. Doğrulama tamamlanmadan canlı veri değiştirilmez; işlem yönetici parolasının yeniden girilmesini gerektirir. Varsayılan limitler yüklenen ZIP için 256 MB, açılmış içerik için 512 MB ve 5.000 dosyadır.

Geri yükleme, mevcut `state`, `blog`, `uploads` ve `branding` içeriğini yedekteki sürümle tamamen değiştirir. İşlemden önce güncel bir yedek indirin. ZIP dosyası uygulama kodunu, `.env` değerlerini veya yönetici parolasını içermez.

Admin ZIP yedeği uygulama verisini taşımak ve elle geri yüklemek içindir. Dokploy control-plane ve named volume yedekleriyle birlikte kullanılmalı, onların yerine geçmemelidir.

## Davranış ve Sınırlar

- İletişim formu veriyi sunucuya göndermez veya saklamaz; ziyaretçinin kendi e-posta uygulamasını alıcı, konu ve içerik hazırlanmış şekilde açar.
- Normal HTTP isteklerinin toplam üst sınırı 5 MB'tır. Görsel yüklemelerinde PNG, JPG, JPEG, WEBP ve GIF desteklenir.
- `/healthz`, storage ve temel JSON şeması hazırsa `204`, kullanılamıyorsa `503` döndürür.
- Dosya tabanlı read-modify-write modeli genel bir dağıtık kilit kullanmadığından worker, thread ve replica sayısı artırılmamalıdır.
- Yönetim girişi ve iletişim formu için uygulama içi rate limit yoktur; üretimde reverse proxy veya Cloudflare kuralı kullanılmalıdır.

## Test

```bash
python -m pytest -q
```

Mevcut test paketi kimlik doğrulama, CSRF, içerik yönetimi, medya doğrulama, seed başlatma ve güvenli yedek geri yükleme senaryolarını kapsar.

## Üretim

Oracle Cloud, Dokploy ve Cloudflare için eksiksiz kurulum ve Coolify'dan geçiş: [docs/deployment.md](docs/deployment.md).

Dokploy üretim özeti:

| Ayar | Değer |
|---|---|
| Service tipi | Application |
| Build Type | Dockerfile |
| Domain Container Port | `8000` |
| Healthcheck | `/healthz` (`204`) |
| Named volume | `mcv-storage:/app/storage` |
| Replica | `1` |
| Update order | `stop-first` |
| Ortam değişkenleri | Yalnız üç zorunlu secret |

Yeni sürüm yayınlamadan önce admin panelinden uygulama yedeği ve Dokploy üzerinden named volume yedeği alın. `main` branch'ini gönderdikten sonra Dokploy deployment loglarını ve `/healthz` sonucunu doğrulayın; güvenli update ve rollback adımları deployment rehberindedir.

## Proje Yapısı

```text
app/                  Flask uygulaması
app/backup.py         ZIP yedekleme ve güvenli geri yükleme
seed/                 İlk kurulum içeriği
storage/              Çalışma zamanı verisi, Git dışında
tests/                Pytest testleri
docs/deployment.md    Üretim kurulum rehberi
.env.example          Ortam değişkeni şablonu
.dockerignore         Docker build context dışlamaları
Dockerfile            Üretim image tanımı
compose.yaml          Yerel container doğrulaması
run.py                Geliştirme giriş noktası
wsgi.py               Üretim WSGI giriş noktası
```

## Lisans

Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır.
