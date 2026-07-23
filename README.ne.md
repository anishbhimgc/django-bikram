# django-bikram-sambat

Python का लागि विक्रम सम्बत् (नेपाली) मिति, Django र DRF सँग प्रथम-श्रेणीको
एकीकरण सहित।

> 🇬🇧 English मा पढ्न [README.md](README.md) हेर्नुहोस्। यो नेपाली संस्करणले
> उही कुरा बुझाउँछ; कुनै फरक देखिए अङ्ग्रेजी README नै आधिकारिक मानिन्छ।

```python
from django_bikram_sambat import BSDate

BSDate(2081, 1, 1).to_ad()                   # datetime.date(2024, 4, 13)
BSDate.from_ad(datetime.date(2024, 4, 13))   # BSDate(2081, 1, 1)
BSDate.today().strftime("%d %B %Y", lang="ne", numerals="devanagari")
```

```python
from django.db import models
from django_bikram_sambat.django import BSDateField

class Invoice(models.Model):
    issued_on = BSDateField()           # भित्र वास्तविक DATE कोलम बस्छ

Invoice.objects.filter(issued_on__gte=BSDate(2081, 1, 1))  # इन्डेक्स प्रयोग हुन्छ
```

---

## भर पर्नु अघि यो पढ्नुहोस्

एउटा कुरा जानाजान लुकाइएको छैन।

### **प्रमाणित** दायरा २०८४ सालमा टुङ्गिन्छ (१२ अप्रिल २०२८)

विक्रम सम्बत् पात्रोका महिनाका दिनहरू **खगोलीय रूपमा** निर्धारण हुन्छन् — सूर्य
प्रत्येक राशिमा प्रवेश गर्ने क्षणले — र नेपाली पञ्चाङ्गमा वर्षैपिच्छे प्रकाशित
हुन्छन्। यो प्याकेजले **दुई स्वतन्त्र स्रोतसँग मिलान गरेर प्रमाणित** गर्न सकेका
वर्षहरू समावेश गर्छ: **१९७५–२०८४ वि.सं. (1918-04-13 – 2028-04-12 ई.सं.)।**
(२०८४ हाम्रोपात्रोबाट थपिएको, nepali-datetime सँग मिलान गरेर।) पूर्वनिर्धारित
रूपमा, यो दायरा बाहिर यसले अनुमान गर्नुको सट्टा `DateOutOfRange`
त्रुटि उठाउँछ।

गणनाबाट **अनुमान गर्न सकिन्छ, तर ठ्याक्कै होइन** — र त्यही खाडल नै मुख्य कुरा
हो। सूर्य-सिद्धान्त मोडेल (आधिकारिक पात्रोले प्रयोग गर्ने उही गणना) ले प्रमाणित
१०९ वर्षलाई **~८७% महिनासम्म मात्र** ठिक निकाल्छ, बाँकी ठ्याक्कै एक दिनले फरक,
र १०९ मध्ये ५८ वर्ष मात्र पूर्ण सही। बाँकी फरक परम्परागत दिन-सीमा नियम र
समितिको म्यानुअल सुधारका कारण हो — त्यसैले गणना गरिएका वर्षहरू स्पष्ट
**provisional (अस्थायी)** तहका रूपमा दिइन्छन्, तथ्यका रूपमा होइन।

तपाईंलाई २०२७ धेरै नजिक लाग्छ भने (लामो समयका लागि हो नै), तल
[२०८३ पछि](#२०८३-पछि) हेर्नुहोस्।

---

## स्थापना

```bash
pip install django-bikram-sambat          # कोर + Django एकीकरण
pip install django-bikram-sambat[drf]     # djangorestframework पनि ल्याउँछ
```

Python 3.10+ चाहिन्छ। Django केवल `django_bikram_sambat.django` का लागि चाहिन्छ; कोर
`BSDate` प्रकारको **कुनै निर्भरता छैन।**

---

## मुख्य डिजाइन निर्णय

**`BSDateField` ले डाटाबेसमा वास्तविक `date` (ग्रेगोरियन/AD) राख्छ र Python मा
`BSDate` देखाउँछ।** रूपान्तरण सीमामा मात्र, अन्यत्र कहीँ हुँदैन।

धेरैजसो नेपाली मिति लाइब्रेरीले BS लाई स्ट्रिङ (`"2081-01-01"`) वा तीन
पूर्णांक कोलमका रूपमा राख्छन्। दुवैले डाटाबेसको सम्पूर्ण उपयोगिता फालिदिन्छन्:

| | वास्तविक `date` (यो प्याकेज) | BS स्ट्रिङ | y/m/d पूर्णांक |
|---|---|---|---|
| दायराको btree इन्डेक्स | ✅ | ❌ समानता/उपसर्ग मात्र | ⚠️ मिश्रित, दायरा खोज छैन |
| `__gte` / `__lt` / `__range` | ✅ सामान्य तुलना | ❌ महिना लम्बाइमा बिग्रन्छ | ⚠️ OR-of-ANDs |
| `ORDER BY` | ✅ | ❌ | ⚠️ ३-कोलम क्रम |
| `Min` / `Max` / समुच्चय | ✅ | ❌ | ❌ |
| `TruncMonth`, `ExtractYear` | ✅ *(AD मानमा — तल हेर्नुहोस्)* | ❌ | ❌ |
| psql / BI उपकरणबाट पढ्न | ✅ | ⚠️ | ❌ |

BS स्ट्रिङ डाटाबेसले बुझ्ने गरी कालक्रमअनुसार क्रमबद्ध हुँदैन, र कुनै इन्डेक्सले
त्यो समस्या हल गर्न सक्दैन। `BSDateField` ले `models.DateField` लाई subclass
गर्ने भएकाले Django ले पहिले नै दिने हरेक lookup चल्छ — केही पुनर्लेखन गर्नु
पर्दैन।

### जान्नैपर्ने एउटा परिणाम

डाटाबेसतर्फका सबै मिति-कार्य `DateField` बाट सोझै आउँछन्, त्यसैले तिनी भण्डारण
गरिएको **ग्रेगोरियन मानमा** चल्छन् — किनकि कोलममा साँच्चै त्यही हुन्छ।

```python
Invoice.objects.filter(issued_on__year=2024)   # AD साल — १ बैशाख २०८१ मिल्छ
Invoice.objects.filter(issued_on__year=2081)   # केही मिल्दैन
```

`ExtractYear` पनि त्यस्तै हो, तर आफै स्पष्ट देखिन्छ — यसले `2024` फर्काउँछ, जुन
सामान्य पूर्णांक हो र कसैले BS साल भनी बुझ्दैन।

**`TruncMonth` र `TruncYear` भने आफै देखिँदैनन्, त्यसैले यो स्पष्ट भन्नु जरुरी
छ।** तिनले *AD* महिना वा सालको सुरुमा काट्छन्, जुन BS महिना/सालको बीचमा पर्छ।
त्यो नतिजा यही field मार्फत फर्कँदा `BSDate` बन्छ — तर त्यो BS अवधिको सुरु
होइन:

```python
Invoice.objects.annotate(m=TruncMonth("issued_on"))   # १ बैशाख २०८१ →
                                                      # BSDate(2080, 12, 19)
Invoice.objects.annotate(y=TruncYear("issued_on"))    # → BSDate(2080, 9, 16)
```

यो सही AD truncation हो, तर अर्थहीन BS bucket हो। BS अवधि अनुसार समूह बनाउन
तलका दायरा helper प्रयोग गर्नुहोस्, वा Python मा bucket बनाउनुहोस्:

```python
start, end = bs_month_bounds(2081, 1)
Invoice.objects.filter(issued_on__gte=start, issued_on__lt=end).aggregate(Sum("total"))
```

यी सबै documented, tested, र जानाजान गरिएको हो। BS साल अनुसार खोज्न तल पढ्नुहोस्।

---

## BS साल वा महिना अनुसार क्वेरी

जानाजान **`__bs_year` lookup छैन।**

डाटाबेससँग BS पात्रो तालिका छैन, त्यसैले SQL मा BS साल मूल्याङ्कन गर्न या त
१०९-हाँगाको `CASE` (सही, तर planner लाई अपारदर्शी — हरेक क्वेरी sequential
scan बन्छ, टेबल चुपचाप ढिलो हुन्छ), या stored generated column (तपाईंको
एप्लिकेसनको schema निर्णय, field प्रकारको होइन) चाहिन्छ। अर्को विकल्प —
समानतालाई दायरामा बदल्ने — `__bs_year=2081` लाई चल्छ तर `__bs_year__gt`,
`values()`, `annotate()`, `order_by()` लाई चल्दैन, जसले transform लाई कतै सही
कतै गलत बनाइदिन्छ।

कहिलेकाहीँ मात्र सुरक्षित हुने lookup भन्दा कुनै lookup नै नहुनु राम्रो। त्यसैले
प्याकेजले helper दिन्छ — BS साल भनेको AD मितिको निरन्तर दायरा नै हो:

```python
from django_bikram_sambat.django.lookups import bs_year_q, bs_month_q, bs_year_bounds

Invoice.objects.filter(bs_year_q("issued_on", 2081))
Invoice.objects.filter(bs_month_q("issued_on", 2081, 1))
Invoice.objects.filter(bs_year_q("issued_on", 2081), status="paid")
Invoice.objects.exclude(bs_year_q("issued_on", 2081))

bs_year_bounds(2081)   # (date(2024, 4, 13), date(2025, 4, 14)) — अर्ध-खुला
```

यी `issued_on >= %s AND issued_on < %s` मा बन्छन्: एउटा इन्डेक्स दायरा scan,
प्रति-पङ्क्ति काम शून्य।

---

## `BSDate`

अपरिवर्तनीय (`__slots__`), hashable, पूर्ण रूपमा क्रमबद्ध, र
`datetime.date` जस्तै आकारको — त्यसैले नयाँ सिक्नुपर्ने थोरै छ।

```python
d = BSDate(2081, 1, 1)

d.year, d.month, d.day        # 2081, 1, 1
d.to_ad()                     # datetime.date(2024, 4, 13)
d.weekday()                   # 5 — सोमबार==0, datetime जस्तै
d.nepali_weekday()            # 6 — आइतबार==0, छापिएको नेपाली पात्रो जस्तै
d.isoformat()                 # '2081-01-01'  (BS घटक)
d.replace(month=2)            # BSDate(2081, 2, 1)
d.days_in_month               # 31  (महिना २९–३२ दिनका हुन्छन्)

d + datetime.timedelta(days=31)     # BSDate(2081, 2, 1)
BSDate(2081, 2, 1) - d              # datetime.timedelta(days=31)

BSDate.today()
BSDate.from_ad(datetime.date(2024, 4, 13))
BSDate.fromisoformat("2081-01-01")
BSDate.strptime("01 Baishakh 2081", "%d %B %Y")
```

केही जानाजान गरिएका छनौट:

- **`BSDate != datetime.date`, सधैँ**, उही दिन भए पनि। चुपचाप बराबर मान्दा
  dict key र set सदस्यता अस्पष्ट हुन्छ। स्पष्ट रूपमा रूपान्तरण गर्नुहोस्।
- **दिनभन्दा सानो timedelta अस्वीकार** हुन्छ, काटिँदैन — गोलो गर्ने दिशा
  कल गर्नेले अनुमान गर्नुपर्ने कुरा होइन।
- **`replace(year=...)` ले त्रुटि उठाउन सक्छ।** २०८१ जेठ ३२ दिनको छ; २०८२
  जेठ ३१ को। ३२ औँ दिन नहुँदा क्ल्याम्प गर्नुको सट्टा असफल हुन्छ।

### त्रुटिहरू

```
BikramError
└── InvalidBSDate      (ValueError पनि हो)
    └── DateOutOfRange
```

`InvalidBSDate` ले `ValueError` लाई subclass गर्छ, त्यसैले भइरहेका
`except ValueError` block चल्छन्, जबकि `except BikramError` ले ठ्याक्कै यही
प्याकेजका त्रुटि समात्छ।

```python
BSDate(2081, 1, 32)   # InvalidBSDate: 2081-01 मा ३१ दिन मात्र, ३२ छैन
BSDate(2090, 1, 1)    # DateOutOfRange: २०९० प्रमाणित दायरा १९७५..२०८३ बाहिर
```

---

## ढाँचा (Formatting)

भाषा र अङ्कहरू **स्वतन्त्र** स्विच हुन्, किनभने वास्तविक नेपाली कागजातहरूले
यिनलाई स्वतन्त्र रूपमा मिसाउँछन्।

```python
d.strftime("%d %B %Y")                                    # '01 Baishakh 2081'
d.strftime("%d %B %Y", lang="ne")                         # '01 वैशाख 2081'
d.strftime("%d %B %Y", numerals="devanagari")             # '०१ Baishakh २०८१'
d.strftime("%A, %d %B %Y", lang="ne", numerals="devanagari")  # 'शनिबार, ०१ वैशाख २०८१'
```

| निर्देशक | अर्थ |
|---|---|
| `%Y` `%y` | साल (४-अङ्क / २-अङ्क) |
| `%m` `%-m` | महिना, प्याड सहित / बिना |
| `%d` `%-d` | दिन, प्याड सहित / बिना |
| `%B` `%b` | महिनाको नाम, पूरा / छोटो |
| `%A` `%a` | बारको नाम, पूरा / छोटो |
| `%j` | वर्षको कति औँ दिन |
| `%%` | अक्षरशः `%` |

पार्स गर्दा पूर्वनिर्धारित रूपमा दुवै अङ्क प्रणाली स्वीकार्छ
(`numerals="auto"`):

```python
from django_bikram_sambat import parse_bs
parse_bs("२०८१-०१-०१", "%Y-%m-%d")        # (2081, 1, 1)
parse_bs("०१ वैशाख २०८१", "%d %B %Y", lang="ne")
```

`%y` input मा अस्पष्ट छ — दायरा १०९ वर्ष फैलिने भएकाले `75`–`83` दुवै 19xx र
20xx सँग मिल्छन्। यो 20xx तर्फ समाधान हुन्छ। `%Y` प्रयोग गर्नु उत्तम।

---

## Django एकीकरण

### Model field

```python
from django_bikram_sambat.django import BSDateField

class Invoice(models.Model):
    issued_on  = BSDateField(db_index=True)
    due_on     = BSDateField(null=True, blank=True)
    created_on = BSDateField(auto_now_add=True)   # BSDate दिन्छ
```

Assignment ले निश्चित अर्थसहित स्वीकार्छ:

| Input | कसरी पढिन्छ |
|---|---|
| `BSDate(2081, 1, 1)` | जस्ताको तस्तै |
| `datetime.date(2024, 4, 13)` | **ग्रेगोरियन**, रूपान्तरित |
| `"2081-01-01"` | **विक्रम सम्बत्** |

यो असमानता जानाजान हो: `datetime.date` स्पष्ट रूपमा ग्रेगोरियन हो, जबकि यस
field को सन्दर्भमा स्ट्रिङ प्रयोगकर्ताले टाइप गरेको BS मान हो। `dumpdata` ले
BS स्ट्रिङ निकाल्छ, र `loaddata` ले फेरि पढ्छ।

`default=BSDate(2081, 1, 1)` चल्छ — migration serializer दर्ता गरिएको छ।

### Forms

```python
from django_bikram_sambat.django.forms import BSDateField, BSDateInput

class InvoiceForm(forms.ModelForm):
    class Meta:
        model, fields = Invoice, ["issued_on"]
        widgets = {"issued_on": BSDateInput(format="%d %B %Y", lang="ne",
                                            numerals="devanagari")}
```

widget सामान्य text input हो, `<input type="date">` होइन — ब्राउजरको आफ्नै
picker ले ग्रेगोरियन मात्र बोल्छ र मानलाई बदलिदिन्छ। यसले JS date picker का
लागि `data-bs-date="2081-01-01"` attribute निकाल्छ।

**Django admin मा** `BSDateField` ले `AdminDateWidget` पाउँथ्यो (admin ले
`models.DateField` लाई MRO मार्फत त्यहीँ नक्सा गर्छ), जसको `vDateField` class
मा Django को *ग्रेगोरियन* क्यालेन्डर र "Today" बटन जोडिन्छ — जसले ग्रेगोरियन
मिति लेख्थ्यो। अब `formfield()` ले त्यो widget साट्छ।

### मिति picker

```python
# settings.py — picker का लागि मात्र आवश्यक
INSTALLED_APPS = [..., "django_bikram_sambat"]
```

```python
from django_bikram_sambat.django import BSDatePickerInput

widgets = {"issued_on": BSDatePickerInput(lang="ne", numerals="devanagari")}
```

१३ kB को सादा JavaScript (gzip मा ४ kB) — **npm छैन, build step छैन, CDN छैन,
नयाँ dependency छैन।** प्रमाणित क्यालेन्डर १.३ kB को string मा asset भित्रै
राखिएको छ, त्यसैले ब्राउजरले साँच्चै BS गणित गर्छ। एउटा test ले त्यो प्रति
Python तालिकासँग मिल्छ भनी जाँच्छ, र दुवै दायराका सबै ४०,१७८ मितिमा मिल्छन्।

JavaScript बन्द भए पनि field उही text input हो, र picker ले लेखेको हरेक मान
server मा पुनः प्रमाणित हुन्छ।

### Admin list filter

उही MRO खोजले `BSDateField` लाई Django को ग्रेगोरियन `DateFieldListFilter`
दिन्छ। **यो field मा त्यो नचलाउनुहोस् — हरेक bucket ले शून्य row फर्काउँछ।**

list filter ले आफ्ना सीमा query string मार्फत पठाउँछ, त्यसैले ती ISO string
भएर फर्किन्छन् — र यो field मा string भनेको *बिक्रम सम्वत्* मान हो। त्यसैले
ग्रेगोरियन सीमा `2026-07-17` लाई 2026-07-17 **BS** (१९६९ AD) पढिन्छ र केही
मिल्दैन। आजै सिर्जना गरिएको row मा "Today" ले पनि केही देखाउँदैन। label पनि
गलत छ: "This month" ले *ग्रेगोरियन* महिना जनाउँछ, जुन दुई BS महिना र साउनतिर
दुई आर्थिक वर्षसम्म फैलिन्छ:

```
"This month"  →  AD 2026-07-01 .. 2026-08-01  =  BS 2083-03-17 .. 2083-04-16
BS महिना      →  AD 2026-07-17 .. 2026-08-17
```

त्यसैले BS बुझ्ने filter प्रयोग गर्नुहोस् — यसले आफ्ना सीमा ग्रेगोरियन नै
पढ्छ, त्यसैले bucket हरूले साँच्चै काम गर्छन्:

```python
from django_bikram_sambat.django.admin import BSDateFieldListFilter

class InvoiceAdmin(admin.ModelAdmin):
    list_filter = [("issued_on", BSDateFieldListFilter)]
```

⚠️ **`date_hierarchy` भने ढाकिँदैन** — त्यो Django को template tag ले सिधै
`__year`/`__month`/`__day` बनाउँछ, hook गर्ने ठाउँ छैन, त्यसैले **AD** अनुसार
झर्छ। माथिको filter नै प्रयोग गर्नुहोस्।

### DRF

```python
from django_bikram_sambat.django.drf import BSDateField

class InvoiceSerializer(serializers.ModelSerializer):
    issued_on = BSDateField()
    class Meta:
        model, fields = Invoice, ["id", "issued_on"]
```

⚠️ **field स्पष्ट रूपमा नलेखी `ModelSerializer` प्रयोग गर्नुभयो भने** DRF ले
`BSDateField` लाई आफ्नै `DateField` मा बदल्छ (किनकि यो `models.DateField` को
subclass हो) र **ग्रेगोरियन** मिति निकाल्छ — देखिन ठीक, तर गलत पात्रोमा। यो
जाल सुरुमै बन्द गर्नुहोस्:

```python
class MyAppConfig(AppConfig):
    def ready(self):
        from django_bikram_sambat.django.drf import register_serializer_field
        register_serializer_field()
```

यो import मा गरिँदैन, किनभने तेस्रो-पक्षको class लाई import को side effect का
रूपमा बदल्दा test suite क्रम-निर्भर बन्छ।

---

## पात्रो डेटा: स्रोत र प्रमाणित दायरा

**तालिका कहाँबाट आयो।** यो हातले लेखिएको वा उत्पन्न गरिएको होइन। यो दुई
स्वतन्त्र, MIT-अनुमतिपत्र भएका स्रोतबाट निकालेर मिलान गरिएको हो:

1. [`nepali-datetime`](https://pypi.org/project/nepali-datetime/) 1.0.8.5
2. [`bikram-sambat`](https://pypi.org/project/bikram-sambat/) 0.2.0

दुवै अन्ततः नेपाली पञ्चाङ्गबाट आउँछन्। महिनाको लम्बाइ तथ्य हुन्, लेखकत्व होइन;
यहाँका कार्यान्वयनहरू मौलिक हुन्।

**प्रमाणित दायरा: १९७५–२०८३ वि.सं. (1918-04-13 – 2027-04-13 ई.सं.)।** ती १०९
वर्षमा दुवै स्रोत सबै १,३०८ महिना-लम्बाइमा सहमत छन्, र:

- हरेक वर्ष जम्मा ३६५ वा ३६६ दिन हुन्छ;
- हरेक महिना २९–३२ दिनको हुन्छ;
- सबै ३९,८१३ मिति round-trip हुन्छन् (`from_ad(to_ad(d)) == d`);
- लगातार BS दिनहरूले AD बार ठ्याक्कै एक-एकले बढाउँछन्, बीचमा खाली छैन;
- व्युत्पन्न आधारहरू स्वतन्त्र रूपमा प्रकाशित मानसँग मिल्छन्:
  - १ बैशाख **१९७५** वि.सं. = १३ अप्रिल १९१८
  - १ बैशाख **२०००** वि.सं. = **१४ अप्रिल १९४३**
  - १ बैशाख **२०८१** वि.सं. = १३ अप्रिल २०२४
  - १ बैशाख **२०८२** वि.सं. = १४ अप्रिल २०२५

> २००० वि.सं.को आधारबारे टिप्पणी: यसलाई प्रायः *१३* अप्रिल १९४३ भनिन्छ। त्यो
> एक दिन गलत हो। दुवै स्रोत लाइब्रेरी, र सार्वजनिक कन्भर्टरहरूले यसलाई **१४
> अप्रिल १९४३** मा राख्छन्, र सम्पूर्ण १९७५–२०८३ शृङ्खला त्यही मानसँग मात्र
> आफैसँग मिल्छ।

**किन २०८३ मा रोकिन्छ** — यो प्रमाण सकिएको ठाउँमा रोकिन्छ, स्रोत सकिएको ठाउँमा
होइन। `nepali-datetime` ले २१०० सम्म पङ्क्ति बोक्छ, तर २०८४ देखि ती स्पष्ट
बनावटी छन् (२०९६ वि.सं. जम्मा ३६४ दिन देखाउँछ, जुन सम्भव छैन)। दुई तालिका
२०८४ देखि छुट्टिन्छन् र फेरि मिल्दैनन्।

---

## २०८३ पछि

२०२७ नजिक छ। अगाडि बढ्ने दुई इमानदार बाटा छन्, र एउटा जुन दिइँदैन।

### दिइँदैन: "१०० वर्षको प्रमाणित तालिका"

त्यस्तो तालिका **कतै छैन** — कसैसँग छैन। २०८४ वि.सं. यताका महिनाका दिनहरू
आधिकारिक रूपमा प्रकाशित भइसकेका छैनन् (समितिले लगभग एक वर्ष अगाडि मात्र
निकाल्छ)। १०० वर्ष दाबी गर्ने हरेक फाइल या त गणना गरिएको (अनुमान) हो या भरौटी
(`nepali-datetime` को २०८३ पछिको डेटामा **३६४ दिनको वर्ष** छ)। यो प्याकेजले
त्यस्तो ढोंग गर्दैन।

### विकल्प A — प्रकाशित हुँदै जाँदा प्रमाणित तालिका विस्तार गर्ने

समितिले थप वर्ष प्रकाशित गरेपछि:

1. `django_bikram_sambat/calendar_data.py` को `VERIFIED_BS_MONTH_DAYS` मा पङ्क्ति
   थप्नुहोस् र `VERIFIED_MAX_BS_YEAR` बढाउनुहोस्।
2. हरेक नयाँ वर्षलाई **कम्तीमा दुई स्वतन्त्र स्रोत**सँग मिलान गर्नुहोस्।
3. suite चलाउनुहोस् — `tests/` ले ३६५/३६६ जम्मा, २९–३२ महिना सीमा, र
   round-trip जाँच्छ।

यही साँचो समाधान हो। provisional तह त्यसतर्फको पुल हो, विकल्प होइन।

### विकल्प B — अहिले नै गणना गरिएका (provisional) वर्ष सक्रिय गर्ने

२०२७ पछिका मिति आजै चाहिन्छ र अनुमानित महिना **आठमा सात पटक** ठिक हुन्छ
(नत्र ±१ दिन) भन्ने स्वीकार्नुहुन्छ भने, opt-in गर्नुहोस्:

```bash
# import-मा, framework-निरपेक्ष — सुरक्षित बाटो
export DJANGO_BIKRAM_PROVISIONAL_THROUGH_YEAR=2183
```

अब `BSDate(2100, 1, 1)` ले त्रुटि नदिई काम गर्छ। त्यस्ता हरेक मिति **फ्ल्याग**
हुन्छन्:

```python
BSDate(2100, 1, 1).is_verified          # False
# बनाउँदा वा रूपान्तरण गर्दा ProvisionalDateWarning उठ्छ
```

आफैँ अंक निकाल्न, वा आफ्नै startup बाट जोड्न चाहनुहुन्छ भने:

```python
from django_bikram_sambat.predict import build_provisional_table, validate

validate()                       # इमानदार backtest: ~८७% महिना, ±१ दिन
table = build_provisional_table(through_year=2183)   # {2084: (...), ...}

from django_bikram_sambat.calendar_data import install_provisional
install_provisional(table)       # startup मा एकपटक, पहिलो मिति-कार्य अघि
```

⚠️ **एक दिनको फरकले फरक पार्ने ठाउँमा** (भुक्तानी मिति, कानुनी म्याद)
provisional मिति **नचलाउनुहोस्**; योजना र display का लागि चलाउनुहोस्, र प्रकाशित
भएपछि प्रमाणित पङ्क्तिले बदल्नुहोस्।

चेतावनी बन्द/कडा गर्न:

```python
import warnings
from django_bikram_sambat import ProvisionalDateWarning
warnings.filterwarnings("ignore", category=ProvisionalDateWarning)  # बन्द
warnings.filterwarnings("error",  category=ProvisionalDateWarning)  # फेरि कडा
```

---

## विकास (Development)

```bash
pip install -e ".[dev]"
pytest
ruff check django_bikram_sambat/
mypy django_bikram_sambat/
```

---

## जानाजान दायरा बाहिर

- **BS समय/datetime प्रकार।** पात्रोले दिन परिभाषित गर्छ, घडी होइन। क्षणका
  लागि सामान्य `DateTimeField` प्रयोग गर्नुहोस्।
- **`__bs_year` / `__bs_month` transform।** माथि हेर्नुहोस्।
- **आर्थिक वर्ष helper, चाडपर्व पात्रो, पञ्चाङ्ग तिथि।** फरक समस्या, फरक
  स्रोत।

## अनुमतिपत्र

MIT। [LICENSE](LICENSE) हेर्नुहोस्।
