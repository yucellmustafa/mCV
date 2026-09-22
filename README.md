# mCV

Flask ile geliştirilmiş, yönetim panelli kişisel özgeçmiş, portfolyo ve blog uygulaması.

![mCV ekran görüntüsü](https://github.com/user-attachments/assets/e8ef9cf5-8b14-4685-87c9-e351c744f0f5)

## Özellikler

- Özgeçmiş, yetenek, proje ve iletişim bölümleri
- Markdown tabanlı blog, arama ve etiket filtreleme
- İçerik, mesaj ve görsel yönetim paneli
- CSRF koruması ve doğrulanan görsel yükleme
- Docker healthcheck ve kalıcı veri volume'u
- Masaüstü ve mobil uyumlu arayüz

## Yapılandırma

Uygulamanın yalnızca üç zorunlu ortam değişkeni vardır:

```dotenv
SECRET_KEY='uretme-komutunun-ciktisini-buraya-yapistirin'
ADMIN_USERNAME='yonetici'
ADMIN_PASSWORD='benzersiz-ve-guclu-bir-parola'
```

`SECRET_KEY` üretmek için:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Eksik veya boş bir değerle uygulama başlamaz. `.env` dosyası Git ve Docker build context dışında tutulur.

## Yerel Geliştirme

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

Site `http://127.0.0.1:5000`, yönetim girişi `http://127.0.0.1:5000/admin/giris` adresindedir. `run.py` yalnız geliştirme için debug modunu açar ve güvenli cookie zorunluluğunu yerel HTTP için kapatır.

## Docker Doğrulaması

`compose.yaml`, yerel image ve volume doğrulaması içindir:

Henüz oluşturmadıysan `.env.example` dosyasını `.env` olarak kopyala, üç değeri doldur ve dosya iznini `600` yap.

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

İlk açılışta `seed/` içeriği `storage/` dizinine kopyalanır. Sonraki açılışlar mevcut veriyi değiştirmez.

```text
storage/
├── state/       Site ayarları ve mesajlar
├── blog/        Markdown yazıları
├── uploads/     Proje ve blog görselleri
└── branding/    Profil görseli ve favicon
```

Docker ve Coolify yalnız `/app/storage` yolunu kalıcı volume olarak bağlar. Dosya tabanlı veri modeli nedeniyle uygulama tek worker, tek thread ve tek replica ile çalışır.

## Test

```bash
python -m pytest -q
```

## Üretim

Oracle Cloud, Coolify ve Cloudflare için eksiksiz kurulum: [docs/deployment.md](docs/deployment.md).

Coolify üretim özeti:

| Ayar | Değer |
|---|---|
| Build Pack | Dockerfile |
| Container portu | `8000` |
| Healthcheck | `/healthz` |
| Kalıcı volume | `/app/storage` |
| Replica | `1` |
| Ortam değişkenleri | Yalnız üç zorunlu secret |

## Proje Yapısı

```text
app/                  Flask uygulaması
seed/                 İlk kurulum içeriği
storage/              Çalışma zamanı verisi, Git dışında
tests/                Pytest testleri
docs/deployment.md    Üretim kurulum rehberi
Dockerfile            Üretim image tanımı
compose.yaml          Yerel container doğrulaması
run.py                Geliştirme giriş noktası
wsgi.py               Üretim WSGI giriş noktası
```

## Lisans

Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır.
