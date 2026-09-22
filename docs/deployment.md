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
| Healthcheck path | `/healthz` |
| Replica | `1` |
| Stop Grace Period | `70` saniye |
| Consistent Container Names | Açık |

`Consistent Container Names`, dosya tabanlı storage kullanan eski ve yeni container'ların rolling deployment sırasında aynı anda çalışmasını engeller. Bu uygulamada kapatılmamalıdır.

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

Başlatma işareti oluşturulduktan sonra yeni deployment seed içeriğini production verisinin üzerine yazmaz.

Preview deployment açılacaksa production volume'unu ve production secret'larını paylaşma.

## 9. Domain ve İlk Deployment

Coolify Domains alanına container hedef portuyla birlikte yaz:

```text
https://example.com:8000,https://www.example.com:8000
```

Buradaki `:8000` public port değildir; Coolify proxy'nin container içinde bağlanacağı porttur. Ziyaretçiler standart HTTPS `443` portunu kullanır.

İlk deployment'ı başlat ve loglarda şu aşamaları doğrula:

- Docker image başarıyla oluşturuldu.
- Storage ilk kez hazırlandı.
- Gunicorn `0.0.0.0:8000` üzerinde başladı.
- Container healthcheck healthy oldu.
- Domain geçerli Let's Encrypt sertifikasıyla açıldı.

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

Oracle port kontrolünde `8000`, `6001` ve `6002` dışarıdan kapalı olmalıdır.

## 11. Cloudflare Güvenlik Kuralları

Minimum öneriler:

- `/admin/giris` için rate limit veya Managed Challenge uygula.
- `/iletisim` POST istekleri için rate limit uygula.
- `/admin/*` ve dinamik HTML üzerinde Cache Everything kullanma.
- `/media/branding/*` için cache bypass veya düşük TTL kullan.
- `/media/*` için Cache Everything kullanma; uygulama silinen dosyaların edge cache'te kalmaması için yeniden doğrulama ister.

Profil ve favicon sabit isimle güncellendiği için değişiklik sonrasında Cloudflare cache purge gerekebilir.

## 12. Yedekleme

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

En az bir volume arşivini ayrı bir test resource'una elle geri yükleyerek doğrula. İndirilmemiş ve geri yüklenmemiş backup doğrulanmış sayılmaz.

## 13. Güncelleme ve Bakım

- İlk başarılı yayından sonra Auto Deploy'u aç.
- Deployment ve backup failure bildirimlerini Telegram veya e-posta ile gönder.
- Coolify güncellemeden önce instance backup al.
- Docker Cleanup eşiğini yüzde 80 kullan.
- Delete Unused Volumes seçeneğini kapalı tut.
- Sunucuyu dışarıdan bir uptime servisiyle izle.
- Production veritabanlarını ve yönetim portlarını internete açma.

Dosya tabanlı storage ile worker, thread veya replica sayısını artırma. Daha yüksek paralellik gerektiğinde veriyi PostgreSQL gibi transaction destekli bir sisteme taşı.

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
| ARM64 build hatası | Bağımlı image veya paketin `linux/arm64` desteğini kontrol et |

## Resmi Kaynaklar

- [Coolify self-hosted installation](https://coolify.io/docs/start-with-self-hosted)
- [Coolify Dockerfile deployment](https://coolify.io/docs/applications/builds/dockerfile)
- [Coolify persistent storage](https://coolify.io/docs/applications/configuration/persistent-storage)
- [Coolify rolling updates](https://coolify.io/docs/applications/deployments/rolling-updates)
- [Coolify firewall](https://coolify.io/docs/core/infrastructure/servers/firewall)
- [Cloudflare Full strict](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/)
- [Oracle network security rules](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securityrules.htm)
