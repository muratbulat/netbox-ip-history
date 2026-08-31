# NetBox IP History — Kurulum Kılavuzu

Paket: `netbox-ip-history` (PyPI) · Eklenti modülü: `netbox_ip_history` · Migration app etiketi: `netbox_ip_history`

## 1. Gereksinimler

- **NetBox sürümleri:** Eklenti `min_version = "4.0.0"`, `max_version = "4.99.99"` bildirir (`netbox_ip_history/__init__.py`), ancak yalnızca belirli sürümler fiilen doğrulanmıştır. Güncel kanıt matrisi için [`COMPATIBILITY.md`](../COMPATIBILITY.md) dosyasına bakın — bildirilen aralık içinde olması, doğrulanmamış bir NetBox sürümünün sorunsuz çalışacağı anlamına gelmez.
- **Python sürümleri:** 3.10, 3.11 veya 3.12 (`pyproject.toml` classifiers; `requires-python >= 3.10`).
- **Sanal ortam:** Eklenti mutlaka NetBox'ın kendi Python sanal ortamına kurulmalıdır (genellikle `/opt/netbox/venv`), sistem Python'ına asla kurulmamalıdır.
- **PostgreSQL / Redis:** Eklenti ek bir veritabanı veya cache bağımlılığı getirmez — mevcut NetBox kurulumunuzun kullandığı PostgreSQL ve Redis örneğini kullanır. Ek bir servis gerekmez.
- **İzinler:** Kurulum/güncelleme için NetBox sunucusuna, sanal ortama yazma ve NetBox servislerini (systemd veya Docker Compose) yeniden başlatma yetkisiyle shell erişimi gerekir. Eklentinin web tarafı izinleri (`view_historicalipevent`, `add_historicalipevent`, `delete_historicalipevent`, `view_importjob`, `view_importsource`) sıradan Django model izinleridir; kurulumdan sonra diğer NetBox izinleri gibi kullanıcı/gruplara atanır.
- **Yedekleme önerisi:** Herhangi bir kurulum, güncelleme veya migration adımından önce NetBox PostgreSQL veritabanınızı yedekleyin (örn. `pg_dump`) — normal NetBox yedekleme rutininize ek olarak. Bu eklenti NetBox'ın kendi tablolarını değiştirmez, ancak elde hazır bir yedek varsa herhangi bir Django migration'dan geri dönmek daha kolaydır.

## 2. PyPI / pip ile Kurulum

Production için önerilen kurulum yöntemi budur.

### NetBox sanal ortamını etkinleştirin

```bash
source /opt/netbox/venv/bin/activate
```

### Eklentiyi kurun

```bash
pip install netbox-ip-history
```

### NetBox'ı yapılandırın

Eklentiyi NetBox'ın `configuration.py` dosyasındaki `PLUGINS` listesine ekleyin:

```python
PLUGINS = [
    "netbox_ip_history",
]
```

İsteğe bağlı olarak `PLUGINS_CONFIG` ile varsayılan ayarları değiştirebilirsiniz (aşağıdaki her iki ayar da varsayılan olarak `True`'dur, bu nedenle bu blok yalnızca değeri değiştirmek istiyorsanız gereklidir):

```python
PLUGINS_CONFIG = {
    "netbox_ip_history": {
        "enable_global_search": True,          # IP geçmişini NetBox global aramasına dahil et
        "enable_native_event_tracking": True,   # yerel NetBox IP değişikliklerini gerçek zamanlı kaydet
    }
}
```

### Migration'ları çalıştırın

```bash
python /opt/netbox/netbox/manage.py migrate
```

### Statik dosyaları toplayın

```bash
python /opt/netbox/netbox/manage.py collectstatic --no-input
```

### NetBox servislerini yeniden başlatın

```bash
systemctl restart netbox netbox-rq
```

Gerçek servis adları kuruluma göre değişebilir (Docker Compose, farklı bir init sistemi, özel unit adları) — NetBox WSGI sürecini ve arka plan worker'ını çalıştıran her ne ise onu yeniden başlatın.

### Doğrulayın

```bash
python /opt/netbox/netbox/manage.py check
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```

Ardından tarayıcıda `/plugins/ip-history/` adresinde eklentinin yüklendiğini doğrulayın.

## 3. GitHub Üzerinden Kurulum

Bunu yukarıdaki PyPI akışından tamamen ayrı tutun — aynı ortamda `pip install netbox-ip-history` ile bir GitHub checkout'unu karıştırmayın.

Birbirinden farklı iki GitHub tabanlı kurulum vardır:

- **Production kaynak kurulumu** — belirli bir etiketli commit'i normal (editable olmayan) bir paket olarak kurar. Kaynaktan çalıştırmak istiyor ama bu sunucuda kodu değiştirmeyi düşünmüyorsanız bunu kullanın.
- **Editable/geliştirme kurulumu** — `pip install -e .` ile kurulur; çalışan eklenti çalışma kopyanıza canlı bir bağlantıdır. Yalnızca geliştirme için kullanın; eklentinin çalışmaya devam etmesi için checkout dizini yerinde kalmalıdır ve kod değişiklikleri yeniden kurulum yapmadan etkili olur.

### Production kaynak kurulumu

```bash
source /opt/netbox/venv/bin/activate
pip install "netbox-ip-history @ git+https://github.com/muratbulat/netbox-ip-history.git@main"
```

Tekrarlanabilir bir production kurulumu için `@main` yerine belirli bir etiketi (örn. `@v0.3.1`) sabitleyin.

### Editable/geliştirme kurulumu

```bash
cd /opt
git clone https://github.com/muratbulat/netbox-ip-history.git
cd netbox-ip-history
source /opt/netbox/venv/bin/activate
pip install -e .
```

### Yapılandırma, migration ve doğrulama (her iki yöntem için)

Yukarıdaki PyPI akışıyla aynıdır:

```python
# configuration.py
PLUGINS = [
    "netbox_ip_history",
]
```

```bash
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq
python /opt/netbox/netbox/manage.py check
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```

`/plugins/ip-history/` adresinde doğrulayın.

## 4. Güncelleme — PyPI / pip

```bash
source /opt/netbox/venv/bin/activate
pip install --upgrade netbox-ip-history
```

Ardından sırasıyla:

```bash
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```

`/plugins/ip-history/` sayfasının yüklendiğini doğrulayın, ardından bir sorun görürseniz NetBox ve worker loglarını kontrol edin (`journalctl -u netbox -u netbox-rq` veya platformunuzun eşdeğeri).

Her güncellemeden sonra `collectstatic` mutlaka çalıştırılmalıdır — eklenti kendi statik dosyalarını içerir ve bu adım atlanırsa değişen dosyalar için NetBox "Static Media Failure" hatası verir.

## 5. Güncelleme — GitHub

GitHub/kaynak güncellemelerini PyPI akışından ayrı ele alın.

Güncellemeden önce yerel değişiklikleri kontrol edin:

```bash
cd /opt/netbox-ip-history
git status
```

Yerel değişiklikler varsa önce bunları inceleyin — körü körüne silmeyin. Normal bir güncelleme sırasında asla `git reset --hard` çalıştırmayın; bu, commit edilmemiş çalışmayı sessizce yok eder.

Normal güncelleme akışı:

```bash
cd /opt/netbox-ip-history
git pull --ff-only
source /opt/netbox/venv/bin/activate
pip install -e .
```

`git pull --ff-only`, yerel dalınız ayrışmışsa (otomatik merge/rebase yapmak yerine) işlemi reddeder — bu durumda manuel olarak inceleyip uzlaştırın.

Editable olmayan production yöntemiyle kurulum yaptıysanız (Bölüm 3), `pip install -e .` yerine güncellenmiş checkout'tan yeniden kurun:

```bash
pip install --force-reinstall --no-deps .
```

Ardından, her güncellemede olduğu gibi:

```bash
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```

`/plugins/ip-history/` adresini doğrulayın.

GitHub kaynak kurulumunun senkronize tutulması gereken iki parçası vardır: Git checkout'u (kaynak kod) ve sanal ortamdaki Python paket kaydı (`pip`'in neyin kurulu olduğuna dair kaydı). Editable olmayan bir kurulumda yalnızca yeni commit'leri çekmek yeterli değildir — paketi de yeniden kurmalısınız; editable kurulum (`-e .`) kaynak değişikliklerini otomatik olarak yansıtır ama saf Python mantığı dışındaki her şey için yine de `migrate`/`collectstatic`/yeniden başlatma gerekir.

## 6. Eklentiyi Devre Dışı Bırakma

Eklentiyi kapatmanın yıkıcı olmayan yolu:

1. `configuration.py` dosyasındaki `PLUGINS` listesinden `"netbox_ip_history"` satırını kaldırın veya yorum satırı yapın.
2. NetBox servislerini yeniden başlatın:
   ```bash
   systemctl restart netbox netbox-rq
   ```

Bu işlem eklentinin arayüzünü, API'sini ve arka plan izlemesini devre dışı bırakır, ancak şunları korur:

- kurulu Python paketi,
- eklentinin veritabanı tabloları,
- şimdiye kadar kaydedilmiş tüm geçmiş IP kayıtları.

Daha sonra yeniden etkinleştirmek (satırı geri ekleyip yeniden başlatmak) veri kaybı olmadan tam işlevselliği geri getirir.

## 7. Kaldırma — PyPI / pip

1. `configuration.py` dosyasındaki `PLUGINS` listesinden `"netbox_ip_history"` satırını kaldırın.
2. NetBox'ı yeniden başlatın:
   ```bash
   systemctl restart netbox netbox-rq
   ```
3. NetBox sanal ortamını etkinleştirin:
   ```bash
   source /opt/netbox/venv/bin/activate
   ```
4. Paketi kaldırın:
   ```bash
   pip uninstall netbox-ip-history
   ```

Python paketini kaldırmak, eklentinin veritabanı tablolarını veya geçmiş kayıtlarını **silmez** — bu veriyi de kaldırmanız gerekiyorsa Bölüm 9'a bakın.

## 8. Kaldırma — GitHub

1. `configuration.py` dosyasındaki `PLUGINS` listesinden `"netbox_ip_history"` satırını kaldırın.
2. Editable veya kaynaktan kurulduysa Python paket kaydını kaldırın:
   ```bash
   source /opt/netbox/venv/bin/activate
   pip uninstall netbox-ip-history
   ```
3. NetBox'ı yeniden başlatın:
   ```bash
   systemctl restart netbox netbox-rq
   ```
4. Yalnızca checkout'un artık gerekmediğini doğruladıktan sonra (başka hiçbir sürecin `/opt/netbox-ip-history` dizinine referans vermediğinden emin olarak) kaynak dizinini kaldırın:
   ```bash
   rm -rf /opt/netbox-ip-history
   ```

Python paketini kaldırmadan önce repository dizinini silmeyin — editable bir kurulumda bu, sanal ortamın paket kaydını bozar ve `pip`'i tutarsız bir durumda bırakabilir. Bu adımların hiçbiri kullanıcı verisini silmez; bunun için Bölüm 9'a bakın.

## 9. Veritabanının Tamamen Kaldırılması

**⚠️ TEHLİKE / YIKICI — bu işlem eklentinin sakladığı tüm geçmiş IP kayıtlarını kalıcı olarak siler.**

Normal kaldırma (Bölüm 7–8) eklentinin veritabanı verisinin silinmesini **gerektirmez** ve bu genellikle gerekli değildir — eklenti devre dışı bırakıldığında/kaldırıldığında tablolar zararsız durumda kalır.

Eklentinin tablolarını özellikle kaldırmanız gerekiyorsa, tek güvenli ve desteklenen yöntem, tam olarak bunun için tasarlanmış kendi migration'larını geri almaktır:

```bash
source /opt/netbox/venv/bin/activate
python /opt/netbox/netbox/manage.py migrate netbox_ip_history zero
```

Bu komut eklentinin 6 migration'ını (`0001`–`0006`) tersine çalıştırır ve tablolarını (`ImportSource`, `ImportJob`, `HistoricalIPEvent`) siler. Hiçbir yerel NetBox tablosuna dokunmaz.

Bunu yalnızca eklenti paketi zaten kaldırıldıktan veya `PLUGINS` artık ona referans vermediğinden sonra ve geçmiş IP kayıtlarına artık ihtiyaç olmadığını ekibinizle ve taze bir veritabanı yedeğiyle karşılaştırarak doğruladıktan sonra yapın. Bu işlem çalıştıktan sonra geri alma yoktur. Farklı bir rollback komutu uydurmaya çalışmayın; migration'lar zaten güvenli bir yol sağlar.

## 10. Doğrulama

Her kurulum veya güncellemeden sonra çalıştırın:

```bash
python /opt/netbox/netbox/manage.py check
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```

Ayrıca kontrol edin:

- NetBox servis durumu: `systemctl status netbox`
- Worker durumu: `systemctl status netbox-rq`
- Eklentinin hatasız yüklendiği: `/plugins/ip-history/` adresini ziyaret edin
- Bir NetBox IP adresi detay sayfasında (`/ipam/ip-addresses/<id>/`) **IP History** butonunun/sekmesinin göründüğü
- Statik dosyaların yüklendiği (tarayıcı konsolu/Network sekmesi temiz, bozuk CSS veya JS yok)
- Uyarılar için NetBox ve worker logları: `journalctl -u netbox -u netbox-rq` (veya platformunuzun eşdeğeri)

**"Static Media Failure"** uyarısı hemen her zaman kurulum/güncelleme sonrası `collectstatic` çalıştırılmadığı veya web sunucusunun statik dosya yolu/izinlerinin yanlış yapılandırıldığı anlamına gelir — genellikle eklentinin kendisinin bozuk olduğu anlamına gelmez.

## 11. Sorun Giderme

### Eklenti görünmüyor

Sırasıyla kontrol edin:

1. `configuration.py` dosyasındaki `PLUGINS` listesinde gerçekten `"netbox_ip_history"` var mı.
2. NetBox'ın kendi sanal ortamına kurdunuz mu, sistem Python'ına değil.
3. Paket gerçekten kurulu mu: `pip show netbox-ip-history`.
4. NetBox başlangıç logları bir import hatası gösteriyor mu: `journalctl -u netbox -n 100`.

### Migration hataları

```bash
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```

Uygulanmış olması gereken ama `[ ]` olarak (uygulanmamış) görünen bir migration, `migrate` komutunun tamamlanmadığını gösterir — yeniden çalıştırın ve hata çıktısını okuyun; migration'ları atlamayın veya sahte olarak uygulanmış işaretlemeyin.

### Static Media Failure

```bash
python /opt/netbox/netbox/manage.py collectstatic --no-input
```

Hata devam ederse web sunucunuzun statik dosya eşlemesinin (örn. nginx `location /static/`) NetBox'ın `STATIC_ROOT` dizinini gösterdiğini ve web sunucusu sürecinin bu dosyaları gerçekten okuyabildiğini (sahiplik/izinler, üst dizinlerdeki geçiş izni dahil) doğrulayın.

### Import/modül hatası

```bash
pip show netbox-ip-history
which python
```

Buradaki `pip`/`python`'un **NetBox sanal ortamını** (`/opt/netbox/venv/...`) işaret ettiğini, sistem veya ilgisiz bir Python kurulumunu değil doğrulayın — "eklenti kurulu ama NetBox bulamıyor" sorununun en yaygın nedeni budur.

### Servis hataları

```bash
systemctl status netbox
systemctl status netbox-rq
journalctl -u netbox -n 100 --no-pager
```

Servis unit adları kuruluma göre değişir; platformunuzun tanımladığı adları kullanın.

## 12. Çevrimdışı / İnternetsiz Kurulum

NetBox sunucusunun internet erişimi yoksa, doğrudan sunucu üzerinde `pip install netbox-ip-history` veya bir git clone'dan `pip install -e .` çalıştırmayı denemeyin — ikisi de PyPI/GitHub'a erişim gerektirir. Bunun yerine, paketi internet bağlantısı olan bir makinede bir kez derleyin ve yalnızca sonuçta oluşan wheel dosyasını aktarın.

### İnternet bağlantılı bir geliştirme/derleme makinesinde

```bash
git clone https://github.com/muratbulat/netbox-ip-history.git
cd netbox-ip-history
python -m pip install --upgrade build
python -m build
```

Bu komut, `pyproject.toml` dosyasında tanımlanan standart Python derleme araç zincirini kullanarak `dist/netbox_ip_history-<versiyon>-py3-none-any.whl` (ve bir `.tar.gz` sdist) üretir — özel bir paketleme adımı gerekmez ve desteklenmez.

### Aktarım

Yalnızca wheel dosyasını, ortamınızın izin verdiği herhangi bir aktarım yöntemiyle (bir atlama sunucusu üzerinden `scp`, taşınabilir medya, dahili bir artifact deposu vb.) internetsiz sunucuya kopyalayın:

```bash
scp dist/netbox_ip_history-<versiyon>-py3-none-any.whl user@netbox-host:/tmp/
```

### İnternetsiz NetBox sunucusunda

```bash
source /opt/netbox/venv/bin/activate
pip install --no-index /tmp/netbox_ip_history-<versiyon>-py3-none-any.whl
```

`--no-index`, pip'in yalnızca yerel dosyadan kurulum yapmasını sağlar; asla PyPI'ye erişmeye çalışmaz. Bu eklentinin NetBox'ın zaten sağladığının ötesinde hiçbir zorunlu runtime bağımlılığı olmadığından (yukarıdaki Gereksinimler bölümüne bakın), normal bir kurulum için bağımlılık paketleme adımı gerekmez.

Ardından diğer kurulum/güncellemelerle aynı şekilde devam edin: `PLUGINS` yapılandırması, `migrate`, `collectstatic --no-input`, servis yeniden başlatma ve doğrulama (yukarıdaki Bölüm 2 ve 10 değişmeden geçerlidir — yalnızca kurulum komutu farklıdır).

Mevcut bir çevrimdışı kurulumu güncellemek için, yeni versiyonun wheel dosyasıyla bu süreci tekrarlayın ve `pip install --no-index --upgrade /tmp/netbox_ip_history-<yeni-versiyon>-py3-none-any.whl` çalıştırın.

## 13. Hızlı Komut Referansı

```bash
# PyPI kurulumu
source /opt/netbox/venv/bin/activate
pip install netbox-ip-history
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq

# GitHub kurulumu (editable/dev)
cd /opt && git clone https://github.com/muratbulat/netbox-ip-history.git
cd netbox-ip-history
source /opt/netbox/venv/bin/activate
pip install -e .
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq

# PyPI güncelleme
source /opt/netbox/venv/bin/activate
pip install --upgrade netbox-ip-history
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq

# GitHub güncelleme
cd /opt/netbox-ip-history && git status
git pull --ff-only
source /opt/netbox/venv/bin/activate
pip install -e .
python /opt/netbox/netbox/manage.py migrate
python /opt/netbox/netbox/manage.py collectstatic --no-input
systemctl restart netbox netbox-rq

# Devre dışı bırakma (yıkıcı olmayan)
# PLUGINS listesinden "netbox_ip_history" satırını kaldırın, ardından:
systemctl restart netbox netbox-rq

# Kaldırma
source /opt/netbox/venv/bin/activate
pip uninstall netbox-ip-history
systemctl restart netbox netbox-rq

# Doğrulama
python /opt/netbox/netbox/manage.py check
python /opt/netbox/netbox/manage.py showmigrations netbox_ip_history
```
