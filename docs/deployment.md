# Oracle Cloud ve Dokploy Üretim Kurulumu

Bu belge mCV uygulamasının Oracle Cloud üzerinde Dokploy ile çalıştırılması ve Cloudflare üzerinden yayınlanması için üretim prosedürüdür.

## Hedef Mimari

```text
Internet
  -> Cloudflare DNS/CDN
  -> Oracle Cloud NSG :80/:443
  -> Dokploy Traefik
  -> mCV Application container :8000
  -> Docker named volume mcv-storage :/app/storage
```

Uygulama dosya tabanlı kalıcı veri kullanır. Bu nedenle üretimde her zaman tek worker, tek thread, tek replica ve `stop-first` deployment kullanılmalıdır. Uygulama portu host üzerinde yayınlanmaz; yalnız Dokploy Traefik üzerinden erişilir.

## 1. Geçiş Öncesi Yedek

Mevcut Coolify kurulumunu kapatmadan önce:

1. `/admin/yedekleme` sayfasından güncel mCV ZIP yedeğini indir.
2. Mevcut `/app/storage` volume'unun ayrıca altyapı yedeğini al.
3. `SECRET_KEY`, `ADMIN_USERNAME` ve `ADMIN_PASSWORD` değerlerini parola yöneticisinde doğrula.
4. Yedeğin açılabildiğini ve `manifest.json` içerdiğini kontrol et.
5. DNS TTL değerini planlanan geçişten önce düşür.

En güvenli geçiş yeni bir sunucuya Dokploy kurup veriyi admin ZIP ile taşımak ve doğrulamadan sonra DNS'i değiştirmektir. Coolify ve Dokploy aynı sunucuda aynı anda `80/443` portlarını kullanamaz. Aynı sunucu kullanılacaksa tüm yedekleri sunucu dışına aldıktan sonra Coolify proxy tamamen durdurulmalı; bu yöntem planlı kesinti gerektirir.

## 2. Sunucu Gereksinimleri

Önerilen başlangıç kapasitesi:

| Kaynak | Değer |
|---|---|
| İşletim sistemi | Ubuntu 24.04 LTS |
| CPU | En az 2 OCPU, tercihen 4 OCPU |
| RAM | En az 4 GB, tercihen 8 GB |
| Disk | En az 80 GB, yedek ve image büyümesi izlenmeli |
| Mimari | AMD64 veya ARM64 |
| Public IP | Reserved/static IPv4 |

Dokploy resmi minimumu 2 GB RAM ve 30 GB disktir. Image build işlemi de aynı sunucuda yapılacağı için üretimde daha yüksek kapasite kullanmak kilitlenme riskini azaltır.

Oracle Cloud NSG ingress kuralları:

| Kaynak | Protokol | Port | Amaç |
|---|---|---:|---|
| Yönetici IP adresi `/32` | TCP | `22` | SSH |
| `0.0.0.0/0` | TCP | `80` | HTTP ve sertifika doğrulaması |
| `0.0.0.0/0` | TCP | `443` | HTTPS |
| Yönetici IP adresi `/32` | TCP | `3000` | Yalnız ilk Dokploy panel kurulumu |

`8000` portunu NSG, UFW veya Dokploy Advanced Ports üzerinden yayınlama. Tek sunuculu kurulumda Docker Swarm yönetim portlarını internete açma.

## 3. İşletim Sistemi Güvenliği

Sunucuya bağlan ve sistemi güncelle:

```bash
ssh -i ~/.ssh/oracle.key ubuntu@PUBLIC_IP
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Üretim güvenlik tabanı:

- SSH anahtar doğrulaması kullan; parola girişini ve root SSH girişini kapat.
- Oracle Ubuntu platform image'ında UFW'yi körlemesine etkinleştirme; metadata ve boot volume için gereken Oracle iptables kurallarını koru.
- Fail2Ban veya CrowdSec etkinleştir.
- Otomatik güvenlik güncellemelerini aç.
- Docker'ın host firewall kurallarını değiştirebildiğini unutma; Oracle NSG'yi birincil ağ sınırı olarak kullan. Host firewall değişikliğini Oracle'ın güncel Compute talimatlarına göre test et.
- Docker socket'i TCP üzerinden hiçbir zaman yayınlama.
- Docker log rotation ve disk kullanım alarmı yapılandır.

## 4. Dokploy Kurulumu

Resmi kararlı sürümü kur:

```bash
curl -sSL https://dokploy.com/install.sh | sh
```

Kurulumdan sonra `http://PUBLIC_IP:3000` adresini yalnız yönetici IP'sinden aç ve ilk hesabı hemen oluştur.

İlk güvenlik ayarları:

- Güçlü ve benzersiz panel parolası kullan.
- `Settings -> Profile` altında passkey ve 2FA etkinleştir.
- En az iki kurtarma yöntemi ve 2FA yedek kodu sakla.
- Dokploy paneli için HTTPS domain yapılandır.
- Dokploy control-plane backup'ını etkinleştir.

Panel domaini HTTPS üzerinden doğrulandıktan sonra doğrudan `IP:3000` yayınını kaldır:

```bash
docker service update --publish-rm "published=3000,target=3000,mode=host" dokploy
```

Bu komutu yalnız panel domaini çalışırken uygula. Aksi halde panel erişimini kaybedebilirsin.

## 5. Cloudflare ve Panel Domaini

Cloudflare DNS'te panel için sunucu IP'sine bir `A` kaydı oluştur. İlk Let's Encrypt sertifikası alınırken kaydı geçici olarak **DNS only** tutmak sorun gidermeyi kolaylaştırır.

Dokploy domain/certificate ayarlarında:

- Host: `panel.example.com`
- Path: `/`
- HTTPS: açık
- Certificate: Let's Encrypt

Panel HTTPS üzerinden açıldıktan sonra Cloudflare SSL/TLS modunu **Full (strict)** yap. Flexible kullanma. Ardından kayıt Proxied yapılabilir.

## 6. GitHub Kaynağı ve Application

Dokploy içinde:

1. `mCV` projesi ve `production` environment oluştur.
2. Yeni bir **Application** ekle.
3. GitHub provider veya Git repository ile `https://github.com/yucellmustafa/mCV.git` kaynağını bağla.
4. Branch olarak `main` seç.
5. Build Type olarak `Dockerfile` seç.

Build ayarları:

| Ayar | Değer |
|---|---|
| Build Type | `Dockerfile` |
| Dockerfile Path | `Dockerfile` |
| Docker Context Path | `.` |
| Docker Build Stage | Boş |
| Published Ports | Boş |
| Auto Deploy | İlk doğrulama tamamlanana kadar kapalı |

`compose.yaml` yalnız yerel Docker doğrulaması içindir; Dokploy production kaynağı değildir.

Bu doğrudan Dockerfile build akışı küçük uygulama için en sade başlangıçtır. Build sırasında production sunucusunda CPU/RAM baskısı görülürse image'ı GitHub Actions üzerinde oluşturup değişmez commit SHA etiketiyle GHCR'a gönder; Dokploy Source Type olarak `Docker` kullanıp hazır image'ı dağıt. `latest` etiketi yerine değişmez tag kullanmak hem tekrarlanabilir deployment hem registry tabanlı rollback sağlar.

## 7. Ortam Değişkenleri

Secret key'i güvenilir bir bilgisayarda üret:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Application `Environment` bölümüne yalnız şu service-level runtime değişkenlerini ekle:

| Değişken | Kural |
|---|---|
| `SECRET_KEY` | En az 32 karakter, rastgele |
| `ADMIN_USERNAME` | Başında/sonunda boşluk yok |
| `ADMIN_PASSWORD` | En az 20 karakter, benzersiz |

Bu değerleri Build Time Arguments içine koyma. Mümkünse Dokploy Secrets Provider üzerinden harici bir secret yöneticisinden referansla. Preview veya staging ortamlarında production secret'larını kullanma.

`SECRET_KEY` değiştirilirse mevcut admin session cookie'leri geçersiz olur; storage verisi etkilenmez.

## 8. Kalıcı Volume

İlk deployment öncesinde Application altında `Advanced -> Mounts` bölümüne **Volume Mount** ekle:

| Alan | Değer |
|---|---|
| Volume Name | `mcv-storage` |
| Mount Path | `/app/storage` |

Bind mount kullanma. Dokploy Volume Backups yalnız Docker named volume destekler.

Volume yazılabilir olmalı ve image içindeki `10001:10001` kullanıcısıyla uyumlu olmalıdır. İlk açılışta uygulama aşağıdaki yapıyı hazırlar:

```text
/app/storage/
├── .initialized
├── state/
│   ├── site.json
│   └── messages.json
├── blog/
├── uploads/
└── branding/
    ├── profile.png
    └── favicon.png
```

İlk açılışta seed içeriği yalnız eksik hedeflere kopyalanır. `.initialized` oluştuktan sonra yeni image içindeki seed değişiklikleri mevcut volume'a otomatik birleştirilmez.

## 9. Swarm ve Healthcheck Ayarları

Application `Advanced -> Cluster Settings` altında:

| Ayar | Değer |
|---|---|
| Mode | Replicated |
| Replicas | `1` |
| Global mode | Kapalı |

Dockerfile zaten `/healthz` için healthcheck içerir. Dokploy Swarm Health Check alanı kullanılıyorsa aynı kontrolü tanımla; image içinde `curl` bulunmadığı için resmi örnekteki curl komutunu kullanma:

```json
{
  "Test": [
    "CMD",
    "python",
    "-c",
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
  ],
  "Interval": 30000000000,
  "Timeout": 5000000000,
  "StartPeriod": 15000000000,
  "Retries": 3
}
```

Update Config:

```json
{
  "Parallelism": 1,
  "Delay": 0,
  "FailureAction": "rollback",
  "Monitor": 30000000000,
  "MaxFailureRatio": 0,
  "Order": "stop-first"
}
```

Dokploy dokümanındaki `start-first`/zero-downtime örneğini bu projede kullanma. Eski ve yeni container'ın aynı anda volume'a yazması veri kaybına yol açabilir. Güvenli deployment kısa bir planlı kesinti oluşturur.

İsteğe bağlı başlangıç kaynak sınırları Dokploy'un beklediği ham birimlerle girilmelidir:

| Kaynak | Örnek değer |
|---|---:|
| Memory Reservation | `268435456` byte |
| Memory Limit | `1073741824` byte |
| CPU Reservation | `250000000` nanoCPU |
| CPU Limit | `1000000000` nanoCPU |

Yedek ve Pillow görsel işlemleri için memory limit'i gerçek kullanım grafikleriyle doğrula.

## 10. Uygulama Domaini

Cloudflare DNS'te önce DNS only olarak sunucu IP'sine kayıt oluştur:

| Tür | İsim | Hedef |
|---|---|---|
| A | `@` | Oracle Reserved Public IP |
| CNAME | `www` | `example.com` |

Application `Domains` bölümünde ana domaini oluştur:

| Alan | Değer |
|---|---|
| Host | `example.com` |
| Path | `/` |
| Container Port | `8000` |
| HTTPS | Açık |
| Certificate | Let's Encrypt |

Domain ayarındaki Container Port yalnız Traefik'in container'a yönleneceği iç porttur; host portu yayınlamaz. `Advanced -> Ports` bölümünü boş bırak.

`www.example.com` domainini de ekle ve `Advanced -> Redirects` altında kalıcı `www -> apex` yönlendirmesi tanımla. Sertifikalar çalıştıktan sonra Cloudflare kayıtlarını Proxied yap ve SSL/TLS modunu Full (strict) olarak koru.

## 11. İlk Deployment

`Deploy` çalıştır ve şu kontroller tamamlanmadan production kabul etme:

- Docker image başarıyla oluşturuldu.
- Gunicorn `0.0.0.0:8000` üzerinde başladı.
- Swarm task `running` ve container healthy durumda.
- Traefik domaini container portu `8000` üzerinden açıyor.
- `/healthz` dışarıdan `204` döndürüyor.
- `/app/storage` gerçekten `mcv-storage` volume'una bağlı.

Dışarıdan doğrula:

```bash
curl --fail --silent --show-error --output /dev/null --write-out '%{http_code}\n' https://example.com/healthz
curl --head https://example.com
curl --head https://www.example.com
```

Fonksiyonel kontrol:

1. Ana sayfayı ve blogu aç.
2. `/admin/giris` üzerinden giriş yap.
3. Mevcut bir blog yazısı ve medya URL'sini aç.
4. Bir test görseli yükle ve dışarıdan erişildiğini doğrula.
5. Redeploy çalıştır; içeriğin ve görselin kaldığını doğrula.
6. `/admin/yedekleme` üzerinden ZIP indir ve açılabildiğini kontrol et.
7. Test içeriğini temizle.

İlk doğrulama tamamlandıktan sonra GitHub provider kullanıyorsan General bölümünde Auto Deploy'u aç. Branch'in `main` olduğunu doğrula.

## 12. Coolify'dan Veri Taşıma

Yeni Dokploy deployment'ı doğrulandıktan sonra:

1. Eski siteden alınan mCV ZIP yedeğini hazır tut.
2. Dokploy uygulamasında production admin hesabıyla giriş yap.
3. `/admin/yedekleme` sayfasında ZIP'i ve mevcut admin parolasını kullanarak geri yükle.
4. Site, blog, mesajlar, branding ve upload dosyalarını doğrula.
5. Yeni bir Dokploy Volume Backup al.
6. DNS'i yeni Dokploy sunucusuna yönlendir.
7. Cloudflare cache'i temizle ve dış kontrolleri tekrarla.
8. Eski Coolify sunucusunu yalnız belirlenen geri dönüş süresi tamamlandıktan sonra kapat.

Admin ZIP uygulama kodunu veya secret'ları içermez. Environment değerleri Dokploy'da ayrıca tanımlanmalıdır.

## 13. Cloudflare Güvenliği

Minimum üretim kontrolleri:

- `/admin/giris` için rate limit veya Managed Challenge uygula.
- `/iletisim` POST istekleri için rate limit uygula.
- `/admin/*` ve dinamik HTML üzerinde Cache Everything kullanma.
- `/media/*` için cache bypass veya düşük TTL kullan.
- HSTS'yi yalnız HTTPS tamamen doğrulandıktan sonra etkinleştir.
- Gerekirse Traefik middleware ile HSTS, frame koruması, Referrer-Policy ve CSP ekle.
- Oracle NSG `80/443` kaynaklarını geçiş tamamlandıktan sonra Cloudflare'ın güncel IP aralıklarıyla sınırlandır.

Uygulama `ProxyFix(x_proto=1)` kullanır. Container portu güvenilmeyen istemcilere doğrudan açılırsa sahte `X-Forwarded-Proto` başlığına güvenebilir; bu nedenle trafik yalnız Dokploy Traefik üzerinden gelmelidir.

## 14. Yedekleme Stratejisi

Üç ayrı yedek katmanı kullan:

| Yedek | Kapsam | Kapsamadığı |
|---|---|---|
| Admin mCV ZIP | Site, mesaj, blog, upload, branding | Kod, secret, Dokploy ayarları |
| Dokploy Volume Backup | `mcv-storage` içeriğinin tamamı | Image, environment, Dokploy control-plane |
| Dokploy Backup | `/etc/dokploy` ve `dokploy-postgres` | Application named volume |

### Admin ZIP

ZIP arşivi SHA-256 manifesti içerir fakat şifreli veya dijital imzalı değildir. İletişim mesajları kişisel veri içerebilir; arşivi şifreli, erişimi sınırlı ve sunucu dışı bir yerde sakla.

Geri yükleme mevcut `state`, `blog`, `uploads` ve `branding` dizinlerini tamamen değiştirir. Volume üzerinde mevcut veri, staging kopyası ve geçici ZIP için yeterli boş alan bırak. Büyük yedek işlemleri tek senkron worker'ı geçici olarak meşgul eder; düşük trafik zamanında çalıştır.

### Dokploy Volume Backup

Önce Dokploy'da Cloudflare R2 veya başka bir S3 destination tanımla. R2 örneği:

```text
Endpoint: https://ACCOUNT_ID.r2.cloudflarestorage.com
Bucket: dokploy-backups
Region: auto
Access Key: yalnız bu bucket için yetkili key
Secret Key: yalnız bu bucket için secret
```

Application `Volume Backups` bölümünde:

| Ayar | Değer |
|---|---|
| Name | `mcv-storage-daily` |
| Schedule | `0 3 * * *` |
| Destination | Yapılandırılan S3/R2 destination |
| Service | mCV application |
| Volume | `mcv-storage` |
| Turn off Container | Açık |
| Enabled | Açık |

`Turn off Container` tutarlı JSON, Markdown ve görsel yedeği için zorunludur; kısa bir günlük kesinti oluşturur. R2 lifecycle ile örneğin 30 günlük saklama uygula ve backup failure bildirimi tanımla.

### Dokploy Control-plane Backup

`Web Server -> Backups` altında günlük Dokploy backup'ı oluştur. Bu yedek `/etc/dokploy` ile `dokploy-postgres` veritabanını kapsar; `mcv-storage` için ayrıca Volume Backup gerekir.

En az üç ayda bir ayrı bir test volume'una restore tatbikatı yap. Doğrulanmamış yedeği başarılı kabul etme.

## 15. Volume Geri Yükleme

Dokploy `Volume Backups -> Restore Volume` akışını kullan:

1. Uygulamayı durdur.
2. Kullanımdaki mevcut volume'un ayrıca güvenlik yedeğini al.
3. S3 destination ve doğru backup dosyasını seç.
4. Restore hedefi olarak kullanılacak volume adını doğrula.
5. Hedef volume'un mevcut olmadığından ve hiçbir container tarafından kullanılmadığından emin ol.
6. Restore tamamlandıktan sonra Application mount'unu geri yüklenen volume'a bağla.
7. Sahipliğin `10001:10001` kullanıcısıyla uyumlu olduğunu doğrula.
8. Uygulamayı başlat ve yayın kontrol listesini çalıştır.

Mevcut volume'u silmek gerekiyorsa önce sunucu dışı güvenlik kopyası almadan işlem yapma. Çalışan container'ın kullandığı volume üzerine restore deneme.

## 16. Güncelleme ve Rollback

### Uygulama güncelleme

1. Yerelde `python -m pytest -q` çalıştır.
2. Admin ZIP ve son başarılı Volume Backup durumunu doğrula.
3. Aktif restore/deploy işlemi olmadığını kontrol et.
4. Değişiklikleri `main` branch'ine gönder veya Dokploy'da `Deploy` çalıştır.
5. `stop-first` kesinti boyunca deployment ve application loglarını izle.
6. Healthcheck, ana sayfa, admin girişi, blog ve medya erişimini doğrula.

### Otomatik Swarm rollback

Health Check ve Update Config doğru tanımlandığında yeni task healthcheck'i geçemezse `FailureAction: rollback` önceki service spec'e döner. Bu geri dönüş yalnız container/image durumunu etkiler; volume verisini eski haline getirmez.

### Belirli sürüme manuel rollback

Her deployment sürümüne dönebilmek için Dokploy'da bir Docker registry yapılandır, Application `Deployments -> Rollback Settings` altında rollback'i etkinleştir ve registry seç. Deployment listesindeki ilgili sürümün `Rollback` işlemini kullan.

Veri formatı veya içerik değiştiyse uygulamayı durdurup aynı yayın noktasında alınmış Volume Backup'ı ayrıca geri yükle. Kod rollback ile veri rollback birbirinden bağımsızdır.

## 17. Dokploy Bakımı

Dokploy güncellemesi uygulama deployment'ından ayrıdır. Önce control-plane backup ve volume backup durumunu doğrula, release notlarını incele ve aktif deployment olmadığından emin ol.

Güncel kararlı sürüme yükseltmek için:

```bash
curl -sSL https://dokploy.com/install.sh | sh -s update
```

Güncellemeden sonra panel, Traefik, application task'ı, domainler, backup schedule ve S3 destination durumunu kontrol et.

Dokploy update işleminin Traefik image'ını otomatik olarak yükselttiğini varsayma. Traefik güncellemesini resmi manual-installation prosedürüne göre ayrı bakım penceresinde yap ve routing kesintisi planla.

## Sorun Giderme

| Belirti | Kontrol |
|---|---|
| Container hemen kapanıyor | Üç zorunlu environment değerini ve minimum uzunlukları kontrol et |
| Swarm task başlamıyor | `mcv-storage` mount adını, yolunu ve server üzerindeki gerçek Swarm hatasını kontrol et |
| `502 Bad Gateway` | Domain Container Port değerinin `8000`, Gunicorn bind adresinin `0.0.0.0` olduğunu kontrol et |
| Domain `404` | Application domainini ve Traefik file-system config/loglarını kontrol et |
| Healthcheck başarısız | `/app/storage` yazılabilirliğini ve `/healthz` iç isteğini kontrol et |
| Redeploy sonrası veri kayıp | Named volume'un `/app/storage` yoluna bağlı olduğunu kontrol et |
| Admin login kalıcı olmuyor | HTTPS ve Cloudflare Full (strict) ayarını kontrol et |
| Cloudflare `522` | Oracle NSG `80/443`, DNS IP ve Traefik durumunu kontrol et |
| Cloudflare `526` | Dokploy/Traefik origin sertifikasını ve hostname eşleşmesini kontrol et |
| Yedek indirilemiyor | `mcv-storage` boş alanını ve application loglarını kontrol et |
| Volume Backup görünmüyor | Mount'un bind değil Docker named volume olduğunu kontrol et |
| Volume restore başarısız | Hedef volume'un mevcut veya kullanımda olmadığını kontrol et |
| Deployment veri yarışı riski | Replica `1` ve Update Order `stop-first` olduğunu kontrol et |

## Resmi Kaynaklar

- [Dokploy Installation](https://docs.dokploy.com/docs/core/installation)
- [Dokploy Applications](https://docs.dokploy.com/docs/core/applications)
- [Dokploy Dockerfile Build Type](https://docs.dokploy.com/docs/core/applications/build-type)
- [Dokploy Advanced Settings](https://docs.dokploy.com/docs/core/applications/advanced)
- [Dokploy Domains](https://docs.dokploy.com/docs/core/domains)
- [Dokploy Cloudflare](https://docs.dokploy.com/docs/core/domains/cloudflare)
- [Dokploy Auto Deploy](https://docs.dokploy.com/docs/core/auto-deploy)
- [Dokploy Volume Backups](https://docs.dokploy.com/docs/core/volume-backups)
- [Dokploy Control-plane Backups](https://docs.dokploy.com/docs/core/backups)
- [Dokploy Rollbacks](https://docs.dokploy.com/docs/core/applications/rollbacks)
- [Dokploy Production Hardening](https://docs.dokploy.com/docs/core/guides/production-hardening)
- [Dokploy Manual Installation and Traefik Updates](https://docs.dokploy.com/docs/core/manual-installation)
- [Cloudflare Full strict](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/)
- [Oracle network security rules](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securityrules.htm)
- [Oracle Compute security best practices](https://docs.oracle.com/en-us/iaas/Content/Compute/References/bestpracticescompute.htm)
- [Oracle Ubuntu UFW known issue](https://docs.oracle.com/en-us/iaas/Content/Compute/known-issues.htm#ufw)
