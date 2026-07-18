# छिटो सुरु गर्ने मार्गदर्शन (Quickstart)

यो `django-bikram` प्रयोग गर्ने व्यावहारिक, चरणबद्ध मार्गदर्शन हो। पूरा
सन्दर्भका लागि [README.ne.md](../README.ne.md) हेर्नुहोस्।

> यो लाइब्रेरीले **१९७५–२०८३ वि.सं.** दायराका मिति मात्र समर्थन गर्छ। यसबाहिरका
> मितिले `DateOutOfRange` त्रुटि दिन्छन् — यो जानाजान गरिएको हो (अनुमान गर्दैन)।

---

## चरण १ — स्थापना

```bash
pip install django-bikram          # कोर + Django
pip install django-bikram[drf]     # DRF पनि चाहिए
```

Python 3.10 वा माथि चाहिन्छ। कोर `BSDate` लाई Django चाहिँदैन।

---

## चरण २ — पहिलो मिति र रूपान्तरण

```python
from django_bikram import BSDate
import datetime

# BS मिति बनाउनुहोस्
d = BSDate(2081, 1, 1)

# BS → AD (ग्रेगोरियन)
d.to_ad()                                  # datetime.date(2024, 4, 13)

# AD → BS
BSDate.from_ad(datetime.date(2024, 4, 13)) # BSDate(2081, 1, 1)

# आजको मिति (नेपाल समयअनुसार)
BSDate.today()

# घटकहरू
d.year, d.month, d.day                      # (2081, 1, 1)
d.days_in_month                             # 31  (यस महिनाको दिन)
```

> **किन `today()` नेपाल समय प्रयोग गर्छ?** सर्भर प्रायः UTC मा चल्छ। नेपाल
> UTC+5:45 हो, त्यसैले `datetime.date.today()` ले दिनको एक चौथाइ समय **हिजो**
> देखाउँछ — महिनाको आखिरमा गलत महिनामा पर्न सक्छ। त्यसैले `BSDate.today()` ले
> पूर्वनिर्धारित रूपमा नेपाल समय लिन्छ।

---

## चरण ३ — नेपालीमा देखाउने

भाषा (`lang`) र अङ्क (`numerals`) छुट्टाछुट्टै मिलाउन सकिन्छ:

```python
d = BSDate(2081, 1, 1)

d.strftime("%d %B %Y")                                       # '01 Baishakh 2081'
d.strftime("%d %B %Y", lang="ne")                            # '01 वैशाख 2081'
d.strftime("%d %B %Y", numerals="devanagari")                # '०१ Baishakh २०८१'
d.strftime("%A, %d %B %Y", lang="ne", numerals="devanagari") # 'शनिबार, ०१ वैशाख २०८१'
```

प्रयोग हुने निर्देशकहरू: `%Y %y %m %-m %d %-d %B %b %A %a %j %%`।

---

## चरण ४ — प्रयोगकर्ताको इनपुट पार्स गर्ने

```python
from django_bikram import parse_bs, BSDate

# देवनागरी वा ASCII, दुवै चल्छ (numerals="auto" पूर्वनिर्धारित)
parse_bs("२०८१-०१-०१", "%Y-%m-%d")            # (2081, 1, 1)
parse_bs("01 वैशाख 2081", "%d %B %Y", lang="ne")

# सिधै BSDate मा
BSDate.strptime("2081-01-01", "%Y-%m-%d")     # BSDate(2081, 1, 1)
BSDate.fromisoformat("2081-01-01")            # BSDate(2081, 1, 1)
```

---

## चरण ५ — Django model मा प्रयोग

```python
from django.db import models
from django_bikram.django import BSDateField

class Invoice(models.Model):
    issued_on  = BSDateField(db_index=True)
    due_on     = BSDateField(null=True, blank=True)
    created_on = BSDateField(auto_now_add=True)
```

डाटाबेसमा **वास्तविक `DATE` कोलम** बस्छ (ग्रेगोरियन), तर Python मा `BSDate`
पाइन्छ। यसैले तलका सबै कुरा इन्डेक्ससहित चल्छन्:

```python
# दायरा क्वेरी — सामान्य तुलना, इन्डेक्स प्रयोग हुन्छ
Invoice.objects.filter(issued_on__gte=BSDate(2081, 1, 1))
Invoice.objects.filter(issued_on__range=(BSDate(2081, 1, 1), BSDate(2081, 12, 30)))

# समुच्चय, क्रम
from django.db.models import Max
Invoice.objects.aggregate(Max("issued_on"))
Invoice.objects.order_by("-issued_on")
```

---

## चरण ६ — BS साल/महिना अनुसार क्वेरी

`__bs_year` जस्तो lookup **छैन** (कारण README मा छ)। बरु helper प्रयोग गर्नुहोस्
— यी इन्डेक्स प्रयोग गर्ने अर्ध-खुला दायरा बनाउँछन्:

```python
from django_bikram.django.lookups import bs_year_q, bs_month_q

# २०८१ सालका सबै
Invoice.objects.filter(bs_year_q("issued_on", 2081))

# २०८१ बैशाखका सबै
Invoice.objects.filter(bs_month_q("issued_on", 2081, 1))

# अरू सर्तसँग मिलाउन
Invoice.objects.filter(bs_year_q("issued_on", 2081), status="paid")
Invoice.objects.exclude(bs_year_q("issued_on", 2081))
```

> ⚠️ ध्यान दिनुहोस्: `issued_on__year=2081` ले **केही मिल्दैन**, किनकि
> भण्डारण गरिएको मान ग्रेगोरियन हो (`__year` ले AD साल जाँच्छ)। BS साललाई
> सधैँ माथिका helper प्रयोग गर्नुहोस्।

---

## चरण ७ — DRF (यदि प्रयोग गर्नुहुन्छ भने)

```python
from rest_framework import serializers
from django_bikram.django.drf import BSDateField

class InvoiceSerializer(serializers.ModelSerializer):
    issued_on = BSDateField()          # स्पष्ट रूपमा लेख्नुहोस्
    class Meta:
        model, fields = Invoice, ["id", "issued_on"]
```

**महत्त्वपूर्ण:** `ModelSerializer` मा field स्पष्ट नलेखी छोड्नुभयो भने DRF ले
ग्रेगोरियन मिति निकाल्छ (गलत पात्रो)। सुरुमै यो जाल बन्द गर्नुहोस्:

```python
# apps.py
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = "myapp"
    def ready(self):
        from django_bikram.django.drf import register_serializer_field
        register_serializer_field()
```

---

## सामान्य त्रुटिहरू

```python
BSDate(2081, 1, 32)   # InvalidBSDate — 2081-01 मा ३१ दिन मात्र
BSDate(2090, 1, 1)    # DateOutOfRange — प्रमाणित दायरा (1975..2083) बाहिर
```

> २०८३ पछिका मिति चाहिन्छ? `DJANGO_BIKRAM_PROVISIONAL_THROUGH_YEAR=2183`
> सेट गरेर गणना गरिएका (provisional, ~८७% सही, ±१ दिन) वर्ष सक्रिय गर्न
> सकिन्छ — विवरण [README.ne.md](../README.ne.md#२०८३-पछि) मा।

समात्ने तरिका:

```python
from django_bikram import BikramError, InvalidBSDate, DateOutOfRange

try:
    d = BSDate(year, month, day)
except DateOutOfRange:
    ...   # दायरा बाहिर
except InvalidBSDate:
    ...   # मिति अस्तित्वमै छैन (जस्तै ३२ गते)
except BikramError:
    ...   # यस प्याकेजका बाँकी सबै त्रुटि
```

`InvalidBSDate` ले `ValueError` लाई पनि subclass गर्छ, त्यसैले भइरहेको
`except ValueError` block पनि चल्छ।

---

## अर्को कहाँ?

- पूरा सन्दर्भ: [README.ne.md](../README.ne.md)
- अङ्ग्रेजी (आधिकारिक): [README.md](../README.md)
