# Oracle Cloud Üretim Kurulumu

Bu belge mCV uygulamasının Oracle Cloud üzerinde Coolify ile çalıştırılması ve Cloudflare üzerinden yayınlanması için tek üretim prosedürüdür.

## Hedef Mimari

```text
Internet
  -> Cloudflare DNS/CDN
  -> Oracle Cloud NSG :80/:443
  -> Coolify Proxy
  -> mCV container :8000
  -> mcv-storage volume /app/storage
```

Coolify Docker kurulumu, reverse proxy, sertifika, deployment, log ve yedekleme işlemlerini tek panelden yönetir. Uygulama portu internete doğrudan açılmaz.

## 1. Sunucu Seçimi

Önerilen başlangıç kapasitesi:

| Kaynak | Değer |
|---|---|
| İşletim sistemi | Ubuntu 24.04 LTS |
| CPU | En az 2 OCPU, tercihen 4 OCPU |
| RAM | En az 4 GB, tercihen 8 GB veya üzeri |
| Disk | En az 80 GB boot volume |
| IP | Reserved Public IPv4 |

Oracle Ampere A1 `arm64` kullanılabilir. Resmi Python image'ı ARM64 destekler; ileride eklenecek her Docker image'ının da ARM64 desteği ayrıca doğrulanmalıdır. En geniş image uyumluluğu için AMD64 tercih edilir.

Sunucuyu public subnet içinde oluştur, SSH anahtarını indir ve public IP'yi reserved IP olarak sabitle.

## 2. Oracle Network Security Group

Instance VNIC'ine özel bir Network Security Group bağla. Kurulum sırasındaki stateful ingress kuralları:

| Kaynak | Protokol | Hedef port | Açıklama |
|---|---|---:|---|
| Yönetici IP adresin `/32` | TCP | 22 | SSH |
| `0.0.0.0/0` | TCP | 80 | HTTP ve sertifika doğrulaması |
| `0.0.0.0/0` | TCP | 443 | HTTPS |
| Yönetici IP adresin `/32` | TCP | 8000 | Geçici Coolify panel erişimi |
| Yönetici IP adresin `/32` | TCP | 6001 | Geçici gerçek zamanlı panel bağlantısı |
| Yönetici IP adresin `/32` | TCP | 6002 | Geçici web terminali |

Yönetici public IP adresini öğrenmek için:

```bash
curl -4 ifconfig.me
```

SSH portunu genel internete açma. Uygulamanın `8000` portu için ayrıca Oracle kuralı oluşturma.

## 3. İşletim Sistemi ve Coolify

Sunucuya bağlan:

```bash
ssh -i ~/.ssh/oracle.key ubuntu@PUBLIC_IP
```

Sistemi güncelle:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Tekrar bağlandıktan sonra resmi Coolify kurulumunu çalıştır:

```bash
sudo -i
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

Kurulum Docker Engine dahil gerekli bileşenleri kurar. İşlem tamamlanınca `http://PUBLIC_IP:8000` adresini aç ve ilk yönetici hesabını hemen oluştur.

İlk panel işlemleri:

- Güçlü ve benzersiz parola belirle.
- İki faktörlü doğrulamayı etkinleştir.
- Instance saat dilimini ayarla.
- `/data/coolify/source/.env` dosyasının tamamını şifreli, sunucu dışı bir konuma yedekle.
- Dosyadaki `APP_KEY` değerini ayrıca parola yöneticisine kaydet.
- Coolify instance backup özelliğini etkinleştir.

## 4. Coolify Panel Domaini

Cloudflare DNS'te önce DNS only olarak kayıt oluştur:

| Tür | İsim | Hedef |
|---|---|---|
| A | `panel` | Oracle Reserved Public IP |

Coolify içinde `Settings -> Configuration -> General -> URL` alanını ayarla:

```text
https://panel.example.com
```

Panel geçerli HTTPS sertifikasıyla açıldıktan sonra:

- Cloudflare kaydını Proxied yap.
- Oracle NSG'den `8000`, `6001` ve `6002` kurallarını kaldır.
- Yalnız `22`, `80` ve `443` kurallarını bırak.

## 5. Cloudflare Temel Ayarları

Uygulama DNS kayıtlarını başlangıçta DNS only oluştur:

| Tür | İsim | Hedef |
|---|---|---|
| A | `@` | Oracle Reserved Public IP |
| A | `www` | Oracle Reserved Public IP |

Cloudflare SSL/TLS ayarları:

| Ayar | Değer |
|---|---|
| Encryption mode | Full (strict) |
| Always Use HTTPS | Açık |
| Minimum TLS | TLS 1.2 |
| DNS TTL | Auto |

Flexible SSL kullanma. HSTS'yi yalnız origin sertifikası, HTTPS ve yönlendirmeler tamamen doğrulandıktan sonra etkinleştir. IPv6 sunucu üzerinde eksiksiz çalışmıyorsa `AAAA` kaydı oluşturma.

## 6. GitHub Kaynağını Bağlama

Coolify içinde:

1. `New Project` ile `mCV` projesi oluştur.
2. `production` environment seç.
3. `New Resource` oluştur.
4. Repo gizliyse GitHub App, açıksa Public Repository seç.
5. `https://github.com/yucellmustafa/mCV.git` kaynağını bağla.
6. Branch olarak `main` seç.
7. Build Pack olarak `Dockerfile` seç.

Application ayarları:

| Ayar | Değer |
|---|---|
| Base Directory | `/` |
| Dockerfile Location | `/Dockerfile` |
| Ports Exposes | `8000` |
| Port Mappings | Boş |
| Healthcheck | Dockerfile içindeki `/healthz` kontrolü |
| Replica | `1` |
| Stop Grace Period | `70` saniye |
| Consistent Container Names | Açık |

Dockerfile image'ı 30 saniye aralıklı, 5 saniye timeout, 15 saniye başlangıç süresi ve 3 tekrar kullanan bir `/healthz` kontrolü içerir. Coolify Dockerfile'daki `HEALTHCHECK` tanımını algılar; panelde ikinci ve farklı bir kontrol tanımlama.

`Consistent Container Names`, dosya tabanlı storage kullanan eski ve yeni container'ların aynı anda çalışmasını engeller. Bunun sonucu deployment'ın rolling değil stop-first olması ve kısa bir planlı kesinti yaratmasıdır. Yeni container başlamazsa eski container otomatik trafik vermeye devam etmez; manuel image rollback gerekir. Veri bütünlüğü için bu ayarı kapatma ve deployment'ı düşük trafikli bir bakım aralığında yap.

### Container güvenlik farkları

Coolify bu projeyi Dockerfile application olarak çalıştırır; `compose.yaml` production kaynağı değildir. Bu nedenle Compose içindeki `read_only`, `init`, capability düşürme, `no-new-privileges`, tmpfs ve log rotation ayarları Coolify'a otomatik taşınmaz. Dockerfile yine non-root `10001:10001` kullanıcısını ve tek worker/thread davranışını uygular.

Coolify sürümünün `Custom Docker Options` alanında desteklendiğini doğrulayarak en az `--init`, `--cap-drop=ALL` ve `--security-opt=no-new-privileges` seçeneklerini uygula. Read-only root filesystem kullanıyorsan `/tmp` için en az 320 MB yazılabilir tmpfs tanımla ve `/app/storage` volume'unun yazılabilir kaldığını doğrula. Her değişiklikten sonra image işleme, yedek indirme ve yedek geri yükleme akışlarını staging ortamında test et.

## 7. Uygulama Secret'ları

Secret key'i yerel bilgisayarda üret:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Coolify `Configuration -> Environment Variables` bölümüne yalnız şu üç değeri ekle:

| Değişken | İçerik |
|---|---|
| `SECRET_KEY` | Üretilen rastgele değer |
| `ADMIN_USERNAME` | Yönetici kullanıcı adı |
| `ADMIN_PASSWORD` | En az 20 karakterlik benzersiz parola |

Her üç değer için:

- Runtime Variable açık olmalı.
- Build Variable kapalı olmalı.
- Literal açık olmalı.
- Değerler secret/locked olarak saklanmalı.

Başka uygulama değişkeni ekleme. Port, debug, secure cookie ve Gunicorn davranışı image içinde güvenli değerlerle sabitlenmiştir.

Parola container ortamında düz secret olarak bulunur. Coolify erişimini sınırla, panelde 2FA kullan ve Docker socket erişimini güvenilir yöneticilerle sınırlandır.

## 8. Kalıcı Storage

İlk deployment öncesinde `Configuration -> Persistent Storage` bölümünde bir Volume Mount oluştur:

| Alan | Değer |
|---|---|
| Volume adı | `mcv-storage` |
| Source Path | Boş |
| Destination Path | `/app/storage` |

Directory Mount veya host path kullanma. Docker tarafından yönetilen volume, image içindeki non-root `app` kullanıcısıyla uyumlu başlatılır.

Volume ilk açılışta `seed/` içeriğiyle hazırlanır:

```text
/app/storage/state       Site ayarları ve iletişim mesajları
/app/storage/blog        Markdown blog yazıları
/app/storage/uploads     Yüklenen görseller
/app/storage/branding    Profil görseli ve favicon
```

İlk başlatmada `seed/site.json`, blog yazıları, seed upload'ları ve marka görselleri yalnız eksik hedeflere kopyalanır; mesaj listesi boş oluşturulur. Başlatma işareti oluşturulduktan sonra yeni deployment seed içeriğini production verisinin üzerine yazmaz veya yeni seed dosyalarını volume'a birleştirmez. Mevcut kurulumlara içerik aktarmak için yönetim panelini ya da kontrollü bir yedek/geri yükleme işlemini kullan.

Preview deployment açılacaksa production volume'unu ve production secret'larını paylaşma.

## 9. Domain ve İlk Deployment

Coolify Domains alanına container hedef portuyla birlikte yaz:

```text
https://example.com:8000,https://www.example.com:8000
```

Buradaki `:8000` public port değildir; Coolify proxy'nin container içinde bağlanacağı porttur. Ziyaretçiler standart HTTPS `443` portunu kullanır.

İlk deployment'ı başlat ve loglarda şu aşamaları doğrula:

- Docker image başarıyla oluşturuldu.
- Gunicorn `0.0.0.0:8000` üzerinde başladı.
- Container healthcheck healthy oldu.
- Domain geçerli Let's Encrypt sertifikasıyla açıldı.

Uygulama storage initialization için ayrı bir başarı logu üretmez. İlk deployment sonrasında Coolify terminalinden `/app/storage/.initialized`, `state/site.json`, `state/messages.json`, `branding/profile.png` ve `branding/favicon.png` dosyalarının varlığını; `uploads` dizininin yazılabilir olduğunu doğrula.

Ardından Cloudflare'daki `@` ve `www` kayıtlarını Proxied yap. Coolify'da `www` adresini ana domaine yönlendir.

Son güvenlik adımı olarak Oracle NSG üzerindeki `80/443` kaynaklarını `0.0.0.0/0` yerine Cloudflare'ın güncel IP aralıklarıyla sınırlandır. Güncel listeyi [Cloudflare IP Ranges](https://www.cloudflare.com/ips/) sayfasından al; statik bir kopyayı dokümandan kullanma. Böylece origin IP bilinse bile Cloudflare rate-limit ve güvenlik kuralları atlanamaz.

Bu kısıtlamadan sonra DNS kaydını DNS only yaparsan origin erişimi ve sertifika yenilemesi kesilebilir. Bakım sırasında doğrudan erişim gerekirse yalnız geçici ve kontrollü bir NSG kuralı aç.

## 10. Yayın Kontrolü

Dışarıdan doğrula:

```bash
curl --fail --silent --show-error https://example.com/healthz
curl --head https://example.com
curl --head https://www.example.com
```

Fonksiyonel kontrol:

1. Ana sayfayı ve blogu aç.
2. `/admin/giris` üzerinden giriş yap.
3. Bir test içeriği veya görseli kaydet.
4. Yeniden deployment çalıştır.
5. Kaydedilen içeriğin kaldığını doğrula.
6. İletişim formundan test mesajı gönder.
7. Mesajın yönetim panelinde göründüğünü doğrula.
8. `/admin/yedekleme` üzerinden bir uygulama yedeği indir ve ZIP'in açılabildiğini doğrula.

Production'a doğrulama kaydı eklediysen işlem sonunda test yazısını, görseli ve mesajı temizle.

Oracle port kontrolünde `8000`, `6001` ve `6002` dışarıdan kapalı olmalıdır.

## 11. Cloudflare Güvenlik Kuralları

Minimum öneriler:

- `/admin/giris` için rate limit veya Managed Challenge uygula.
- `/iletisim` POST istekleri için rate limit uygula.
- `/admin/*` ve dinamik HTML üzerinde Cache Everything kullanma.
- `/media/branding/*` için cache bypass veya düşük TTL kullan.
- `/media/*` için Cache Everything kullanma; uygulama silinen dosyaların edge cache'te kalmaması için yeniden doğrulama ister.
- Uygulama içinde login veya iletişim formu rate limit'i olmadığından ilk iki kuralı isteğe bağlı değil, üretim güvenlik kontrolü olarak değerlendir.
- Container portunu yalnız Coolify proxy ağına açık tut. Uygulama bir proxy katmanından gelen `X-Forwarded-Proto` değerine güvenir.
- HSTS, frame koruması, Referrer-Policy ve gerekiyorsa CSP başlıklarını Coolify proxy veya Cloudflare katmanında tanımla ve önce staging ortamında doğrula.

Profil ve favicon sabit isimle güncellendiği için değişiklik sonrasında Cloudflare cache purge gerekebilir.

## 12. Yedekleme

İki tamamlayıcı yedek katmanı kullan:

| Yedek | Temel amaç | Kapsam | Kapsamadığı |
|---|---|---|---|
| Admin mCV ZIP | Taşınabilir uygulama verisi | Site, mesaj, blog, upload ve branding | Kod, secret, Coolify ayarları |
| `mcv-storage` volume | Uygulama felaket kurtarma | `/app/storage` içeriğinin tamamı | Image, environment, Coolify veritabanı |
| Coolify instance | Kontrol düzlemi kurtarma | Coolify veritabanı ve resource ayarları | Uygulama volume'u ve `/data/coolify/source/.env` |

### Uygulama içi taşınabilir yedek

`/admin/yedekleme` sayfasından indirilen sürümlü ZIP şunları içerir:

- Site ayarları ve iletişim mesajları
- Markdown blog yazıları
- Yüklenen görseller
- Profil görseli ve favicon
- Dosya boyutu ve SHA-256 sağlama toplamlarını içeren manifest

ZIP uygulama kodunu, Coolify ayarlarını, `.env` secret'larını veya yönetici parolasını içermez. Arşiv şifrelenmez ve iletişim mesajları kişisel veri içerebilir; indirdikten sonra şifreli ve erişimi sınırlı bir konumda sakla.

Geri yükleme mevcut dört veri dizinini yedekteki içerikle tamamen değiştirir. Yönetici parolası yeniden istenir; arşiv yolu, türü, dosya sayısı, boyutu ve sağlama toplamları canlı veri değiştirilmeden önce doğrulanır. Varsayılan sınırlar 256 MB yüklenen ZIP, 512 MB açılmış veri ve 5.000 dosyadır. İşlem sırasında mevcut veri ile staging kopyası aynı volume'da bulunduğu için volume üzerinde yedek boyutunun en az iki katı kadar güvenli boş alan bırak.

Yedek oluşturma ve geri yükleme tek senkron worker üzerinde çalışır; büyük arşivlerde diğer istekler işlem tamamlanana kadar bekleyebilir. Bu işlemleri düşük trafik zamanında yap, sekmeyi kapatma ve tamamlandıktan sonra uygulama loglarını kontrol et.

Uygulama ZIP'i sürümler arası içerik taşıma ve hızlı elle kurtarma içindir. Altyapı arızası, hatalı volume veya Coolify kaybı için aşağıdaki bağımsız yedeklerin yerine geçmez.

### Coolify ve volume yedeği

Cloudflare R2 üzerinde private bir `coolify-backups` bucket oluştur. Yalnız bu bucket için Object Read & Write yetkili R2 token üret.

Coolify S3 Storage değerleri:

```text
Endpoint: https://ACCOUNT_ID.r2.cloudflarestorage.com
Bucket: coolify-backups
Region: auto
Access Key: R2 Access Key ID
Secret Key: R2 Secret Access Key
```

İki ayrı yedek planı oluştur:

| Yedek | Sıklık | Saklama |
|---|---|---|
| Coolify instance | Günlük | R2 üzerinde 30 kopya |
| `mcv-storage` volume | Günlük | R2 üzerinde 30 kopya |

Volume backup ayarında `Stop containers while creating the archive` seçeneğini aç. Böylece JSON, Markdown ve görseller aynı tutarlı noktadan arşivlenir.

Coolify instance backup uygulama volume'unu ve `/data/coolify/source/.env` dosyasını içermez. Bu dosya şifreli olarak ayrıca yedeklenmeli, `APP_KEY` de parola yöneticisinde tutulmalıdır.

En az bir volume arşivini ayrı bir test resource'una elle geri yükleyerek doğrula. Aynı ortamda uygulama ZIP geri yüklemesini de test et; üretim volume'unu ve secret'larını test resource'uyla paylaşma. İndirilmemiş ve geri yüklenmemiş backup doğrulanmış sayılmaz.

### Volume geri yükleme runbook'u

1. Coolify'da uygulamayı durdur; restore boyunca volume'a yazan container bırakma.
2. Resource ayarından `/app/storage` mount'una bağlı gerçek Docker volume adını kaydet. Görünen kaynak adı Coolify tarafından prefix almış olabilir; tahmin etme.
3. Mevcut volume'un restore öncesi güvenlik arşivini al ve farklı bir konumda sakla.
4. Geri yüklenecek arşivin kök seviyesini doğrula; hedefte doğrudan `.initialized`, `state`, `blog`, `uploads` ve `branding` bulunmalıdır.
5. Önce ayrı bir test volume'una geri yükle. Dosya sahipliğini runtime kullanıcısı `10001:10001` ile uyumlu hale getir.
6. `state/site.json`, `state/messages.json`, `branding/profile.png` ve `branding/favicon.png` dosyalarını doğrula.
7. Test resource'unu ayrı secret'larla başlat; `/healthz`, admin girişi, blog ve medya erişimini kontrol et.
8. Aynı doğrulanmış prosedürü production volume'una uygula, uygulamayı başlat ve yayın kontrol listesini çalıştır.
9. Eski volume veya güvenlik arşivini yalnız doğrulama ve belirlenen saklama süresi tamamlandıktan sonra kaldır.

Coolify sürümüne göre volume arşivi geri yükleme arayüzü değişebilir. Dashboard otomatik restore sunmuyorsa arşivi sunucuda kontrollü olarak aç; çalışan container'ın dosyalarının üzerine doğrudan yazma.

## 13. Güncelleme ve Bakım

### Uygulama güncelleme akışı

1. Değişiklikleri yerelde `python -m pytest -q` ile doğrula.
2. Yönetim panelinden güncel uygulama ZIP'ini indir. Veri modeli veya storage davranışı değişiyorsa container'ı durduran bir `mcv-storage` volume yedeği de al.
3. Önceki çalışan image'ın `Configuration -> Rollback` listesinde bulunduğunu ve aktif başka deploy/restore işlemi olmadığını doğrula.
4. Değişiklikleri `main` branch'ine gönder. Auto Deploy kapalıysa Coolify uygulamasında `Deploy` çalıştır.
5. Stop-first kesinti boyunca build ve başlangıç loglarını izle; yeni container healthy olmadan işlemi başarılı kabul etme.
6. Beklenen commit/image'ın çalıştığını, `/healthz`, ana sayfa, blog, `/admin/giris`, mevcut bir medya URL'si ve yedek indirmeyi doğrula.
7. Admin panelinde daha önce kaydedilmiş içeriğin, mesajların ve görsellerin kaldığını ve loglarda yeni exception bulunmadığını kontrol et.

Yeni image içindeki `seed/` değişikliklerinin mevcut volume'a otomatik uygulanmadığını unutma. İçerik değişikliklerini kod deployment'ı üzerinden production verisine taşımaya çalışma.

### Geri dönüş

Coolify `Configuration -> Rollback` bölümünden önceki çalışan image'ı seçip deploy et. Image rollback yalnız uygulama kodunu geri alır; persistent volume'u, ortam değişkenlerini veya dış servisleri eski haline getirmez.

Güncelleme kalıcı veriyi değiştirdiyse ya da hatalı bir geri yükleme yapıldıysa uygulamayı durdur ve aynı yayın noktasında alınmış `mcv-storage` yedeğini ayrıca geri yükle. Kod ile veri yedeğinin birbiriyle uyumlu olduğundan emin ol. Geri dönüşten sonra sağlık, admin girişi, blog ve medya kontrollerini yeniden çalıştır.

### Sürekli bakım

- İlk başarılı ve doğrulanmış yayından sonra Auto Deploy'u aç.
- Deployment ve backup failure bildirimlerini Telegram veya e-posta ile gönder.
- Coolify güncellemeden önce instance backup al.
- Docker Cleanup eşiğini yüzde 80 kullan.
- Delete Unused Volumes seçeneğini kapalı tut.
- Sunucuyu dışarıdan bir uptime servisiyle izle.
- Production veritabanlarını ve yönetim portlarını internete açma.

Dosya tabanlı storage ile worker, thread veya replica sayısını artırma. Daha yüksek paralellik gerektiğinde veriyi PostgreSQL gibi transaction destekli bir sisteme taşı.

### Coolify kontrol düzlemi bakımı

Coolify güncellemesi mCV application deployment'ından ayrıdır. Güncellemeden önce instance backup'ın güncel olduğunu, `/data/coolify/source/.env` ve `APP_KEY` kopyalarının erişilebilir olduğunu doğrula; release notlarını incele ve aktif application deployment olmadığından emin ol. Güncellemeden sonra beklenen Coolify sürümünü, proxy'yi, sunucu bağlantısını ve tüm resource durumlarını kontrol et. Coolify downgrade uygulama image'ını veya `mcv-storage` verisini geri almaz.

## Sorun Giderme

| Belirti | Kontrol |
|---|---|
| Container hemen kapanıyor | Üç zorunlu secret'ın dolu olduğunu kontrol et |
| `502 Bad Gateway` | Ports Exposes ve domain hedef portunun `8000` olduğunu kontrol et |
| Healthcheck unhealthy | `/app/storage` volume izinlerini ve container loglarını kontrol et |
| Cloudflare `522` | Oracle NSG üzerinde `80/443` kurallarını kontrol et |
| Cloudflare `526` | Coolify origin sertifikasının hostname ve süresini kontrol et; Flexible kullanma |
| Redirect döngüsü | Flexible yerine Full (strict) kullan |
| İçerik deployment sonrası kayboluyor | `/app/storage` Volume Mount bağlantısını kontrol et |
| Admin login kalıcı olmuyor | Siteye HTTPS üzerinden erişildiğini kontrol et |
| Profil veya favicon eski | Cloudflare cache'ini temizle |
| Yedek indirilemiyor | `/app/storage` boş alanını ve container loglarını kontrol et |
| Geri yükleme reddediliyor | ZIP'in mCV manifestini, 256 MB istek sınırını ve yönetici parolasını kontrol et |
| Geri yükleme sırasında alan hatası | Volume'da mevcut veri ve staging kopyası için yeterli boş alan aç |
| ARM64 build hatası | Bağımlı image veya paketin `linux/arm64` desteğini kontrol et |

## Resmi Kaynaklar

- [Coolify self-hosted installation](https://coolify.io/docs/start-with-self-hosted)
- [Coolify Dockerfile deployment](https://coolify.io/docs/applications/builds/dockerfile)
- [Coolify persistent storage](https://coolify.io/docs/applications/configuration/persistent-storage)
- [Coolify rolling updates](https://coolify.io/docs/applications/deployments/rolling-updates)
- [Coolify rollbacks](https://coolify.io/docs/applications/deployments/rollbacks)
- [Coolify firewall](https://coolify.io/docs/core/infrastructure/servers/firewall)
- [Cloudflare Full strict](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/)
- [Oracle network security rules](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securityrules.htm)
