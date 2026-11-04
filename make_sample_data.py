"""
Builds DUMMY input files in sample_data/ so the app can be tried without real data.

  1_source_questions.csv        id, english, hindi
  2_reference_translations.csv  id + 13 language columns (placeholder text, NOT checked by native speakers)
  3_vendor_output.csv           id, source_lang, target_lang, translation
                                (the reference with some words randomly dropped/swapped; NOT a real vendor's output)

Deliberate gaps, to exercise the app's edge cases: no output at all for Manipuri (Meitei), no Hindi-source output
for Urdu, and one missing translation for Odia.

Run:  python make_sample_data.py
"""
import csv
import os
import random

import evaluator as ev

OUT = os.path.join(ev.BASE_DIR, "sample_data")

IDS = ["Q001", "Q002", "Q003", "Q004", "Q005", "Q006"]

ENGLISH = [
    "What is the capital of India?",
    "Which river is the longest in India?",
    "The sum of two numbers is 20 and their difference is 4. Find the numbers.",
    "Who is known as the Father of the Nation?",
    "Water boils at 100 degrees Celsius at sea level.",
    "Choose the correct option from the following.",
]
HINDI = [
    "भारत की राजधानी क्या है?",
    "भारत की सबसे लंबी नदी कौन-सी है?",
    "दो संख्याओं का योग 20 है और उनका अंतर 4 है। संख्याएँ ज्ञात कीजिए।",
    "राष्ट्रपिता के नाम से किसे जाना जाता है?",
    "समुद्र तल पर पानी 100 डिग्री सेल्सियस पर उबलता है।",
    "निम्नलिखित में से सही विकल्प चुनिए।",
]

REFS = {
    "Assamese": ["ভাৰতৰ ৰাজধানী কি?", "ভাৰতৰ আটাইতকৈ দীঘল নদী কোনটো?",
                 "দুটা সংখ্যাৰ যোগফল ২০ আৰু ইহঁতৰ পাৰ্থক্য ৪। সংখ্যা দুটা উলিওৱা।",
                 "ৰাষ্ট্ৰপিতা হিচাপে কাক জনা যায়?", "সাগৰ পৃষ্ঠত পানী ১০০ ডিগ্ৰী চেলছিয়াছত উতলে।",
                 "তলত দিয়াসমূহৰ পৰা শুদ্ধ বিকল্পটো বাছনি কৰক।"],
    "Bengali": ["ভারতের রাজধানী কী?", "ভারতের দীর্ঘতম নদী কোনটি?",
                "দুটি সংখ্যার যোগফল ২০ এবং তাদের বিয়োগফল ৪। সংখ্যা দুটি নির্ণয় করো।",
                "জাতির জনক নামে কে পরিচিত?", "সমুদ্রপৃষ্ঠে জল ১০০ ডিগ্রি সেলসিয়াসে ফোটে।",
                "নিচের মধ্য থেকে সঠিক বিকল্পটি বেছে নাও।"],
    "Gujarati": ["ભારતની રાજધાની કઈ છે?", "ભારતની સૌથી લાંબી નદી કઈ છે?",
                 "બે સંખ્યાઓનો સરવાળો 20 છે અને તેમનો તફાવત 4 છે. સંખ્યાઓ શોધો.",
                 "રાષ્ટ્રપિતા તરીકે કોણ ઓળખાય છે?", "દરિયાની સપાટીએ પાણી 100 ડિગ્રી સેલ્સિયસ પર ઉકળે છે.",
                 "નીચેનામાંથી સાચો વિકલ્પ પસંદ કરો."],
    "Kannada": ["ಭಾರತದ ರಾಜಧಾನಿ ಯಾವುದು?", "ಭಾರತದ ಅತಿ ಉದ್ದದ ನದಿ ಯಾವುದು?",
                "ಎರಡು ಸಂಖ್ಯೆಗಳ ಮೊತ್ತ 20 ಮತ್ತು ಅವುಗಳ ವ್ಯತ್ಯಾಸ 4. ಆ ಸಂಖ್ಯೆಗಳನ್ನು ಕಂಡುಹಿಡಿಯಿರಿ.",
                "ರಾಷ್ಟ್ರಪಿತ ಎಂದು ಯಾರನ್ನು ಕರೆಯಲಾಗುತ್ತದೆ?",
                "ಸಮುದ್ರ ಮಟ್ಟದಲ್ಲಿ ನೀರು 100 ಡಿಗ್ರಿ ಸೆಲ್ಸಿಯಸ್ ತಾಪಮಾನದಲ್ಲಿ ಕುದಿಯುತ್ತದೆ.",
                "ಕೆಳಗಿನವುಗಳಲ್ಲಿ ಸರಿಯಾದ ಆಯ್ಕೆಯನ್ನು ಆರಿಸಿ."],
    "Konkani": ["भारताची राजधानी खंयची?", "भारतांतली सगळ्यांत लांब न्हंय खंयची?",
                "दोन संख्यांची बेरीज 20 आनी तांचो फरक 4. त्या संख्या सोदून काडात.",
                "राष्ट्रपिता म्हूण कोणाक वळखतात?", "दर्याच्या सपाटेर उदक 100 डिग्री सेल्सियसार उकळटा.",
                "सकयल दिल्ल्यांतल्यान बरो पर्याय वेंचून काडात."],
    "Malayalam": ["ഇന്ത്യയുടെ തലസ്ഥാനം ഏതാണ്?", "ഇന്ത്യയിലെ ഏറ്റവും നീളം കൂടിയ നദി ഏതാണ്?",
                  "രണ്ട് സംഖ്യകളുടെ തുക 20 ഉം വ്യത്യാസം 4 ഉം ആണ്. സംഖ്യകൾ കണ്ടെത്തുക.",
                  "രാഷ്ട്രപിതാവ് എന്നറിയപ്പെടുന്നത് ആരാണ്?",
                  "സമുദ്രനിരപ്പിൽ വെള്ളം 100 ഡിഗ്രി സെൽഷ്യസിൽ തിളയ്ക്കുന്നു.",
                  "ചുവടെ നൽകിയിരിക്കുന്നവയിൽ നിന്ന് ശരിയായ ഓപ്ഷൻ തിരഞ്ഞെടുക്കുക."],
    "Manipuri (Meitei)": ["ꯏꯟꯗꯤꯌꯥꯒꯤ ꯔꯥꯖꯙꯥꯅꯤ ꯀꯔꯤꯅꯣ?", "ꯏꯟꯗꯤꯌꯥꯗꯥ ꯌꯥꯝꯅ ꯁꯥꯡꯕꯥ ꯇꯨꯔꯦꯜ ꯀꯔꯤꯅꯣ?",
                          "ꯃꯁꯤꯡ ꯑꯅꯤꯒꯤ ꯁꯔꯨꯛ ꯲꯰ ꯑꯣꯏꯅꯤ ꯑꯃꯁꯨꯡ ꯃꯈꯥꯒꯤ ꯈꯟꯅꯕꯥ ꯴ ꯑꯣꯏꯅꯤ꯫ ꯃꯁꯤꯡ ꯑꯗꯨ ꯊꯤꯕꯤꯌꯨ꯫",
                          "ꯂꯥꯎꯊꯣꯛꯀꯤ ꯃꯄꯥ ꯍꯥꯌꯅꯥ ꯀꯅꯥꯕꯨ ꯀꯧꯕꯅꯣ?", "ꯁꯃꯨꯗ꯭ꯔꯒꯤ ꯃꯈꯥꯗꯥ ꯏꯁꯤꯡ ꯗꯤꯒ꯭ꯔꯤ ꯁꯦꯜꯁꯤꯌꯁ ꯱꯰꯰ꯗꯥ ꯊꯥꯗꯣꯛꯀꯅꯤ꯫",
                          "ꯃꯈꯥꯗꯥ ꯌꯥꯕꯤꯔꯤꯕꯥ ꯃꯅꯨꯡꯗꯒꯤ ꯑꯆꯨꯝꯕꯥ ꯑꯣꯞꯁꯟ ꯈꯅꯕꯤꯌꯨ꯫"],
    "Marathi": ["भारताची राजधानी कोणती?", "भारतातील सर्वात लांब नदी कोणती आहे?",
                "दोन संख्यांची बेरीज 20 आहे आणि त्यांचा फरक 4 आहे. त्या संख्या शोधा.",
                "राष्ट्रपिता म्हणून कोणाला ओळखले जाते?", "समुद्रसपाटीवर पाणी 100 अंश सेल्सिअसवर उकळते.",
                "खालीलपैकी योग्य पर्याय निवडा."],
    "Odia": ["ଭାରତର ରାଜଧାନୀ କେଉଁଟି?", "ଭାରତର ସବୁଠାରୁ ଲମ୍ବା ନଦୀ କେଉଁଟି?",
             "ଦୁଇଟି ସଂଖ୍ୟାର ସମଷ୍ଟି 20 ଏବଂ ସେମାନଙ୍କ ଅନ୍ତର 4। ସଂଖ୍ୟା ଦୁଇଟି ନିର୍ଣ୍ଣୟ କର।",
             "ରାଷ୍ଟ୍ରପିତା ଭାବେ କାହାକୁ ଜଣାଯାଏ?", "ସମୁଦ୍ର ପୃଷ୍ଠରେ ପାଣି 100 ଡିଗ୍ରୀ ସେଲସିୟସରେ ଫୁଟେ।",
             "ନିମ୍ନରୁ ସଠିକ୍ ବିକଳ୍ପଟି ବାଛନ୍ତୁ।"],
    "Punjabi": ["ਭਾਰਤ ਦੀ ਰਾਜਧਾਨੀ ਕਿਹੜੀ ਹੈ?", "ਭਾਰਤ ਦੀ ਸਭ ਤੋਂ ਲੰਬੀ ਨਦੀ ਕਿਹੜੀ ਹੈ?",
                "ਦੋ ਸੰਖਿਆਵਾਂ ਦਾ ਜੋੜ 20 ਹੈ ਅਤੇ ਉਨ੍ਹਾਂ ਦਾ ਅੰਤਰ 4 ਹੈ। ਸੰਖਿਆਵਾਂ ਪਤਾ ਕਰੋ।",
                "ਰਾਸ਼ਟਰ ਪਿਤਾ ਵਜੋਂ ਕਿਸ ਨੂੰ ਜਾਣਿਆ ਜਾਂਦਾ ਹੈ?", "ਸਮੁੰਦਰ ਤਲ ਉੱਤੇ ਪਾਣੀ 100 ਡਿਗਰੀ ਸੈਲਸੀਅਸ ਉੱਤੇ ਉੱਬਲਦਾ ਹੈ।",
                "ਹੇਠ ਲਿਖਿਆਂ ਵਿੱਚੋਂ ਸਹੀ ਵਿਕਲਪ ਚੁਣੋ।"],
    "Tamil": ["இந்தியாவின் தலைநகரம் எது?", "இந்தியாவின் மிக நீளமான நதி எது?",
              "இரண்டு எண்களின் கூட்டுத்தொகை 20 மற்றும் அவற்றின் வித்தியாசம் 4. அந்த எண்களைக் கண்டுபிடிக்கவும்.",
              "தேசத்தந்தை என்று அழைக்கப்படுபவர் யார்?", "கடல் மட்டத்தில் தண்ணீர் 100 டிகிரி செல்சியஸில் கொதிக்கிறது.",
              "பின்வருவனவற்றில் சரியான விருப்பத்தைத் தேர்ந்தெடுக்கவும்."],
    "Telugu": ["భారతదేశ రాజధాని ఏది?", "భారతదేశంలో అత్యంత పొడవైన నది ఏది?",
               "రెండు సంఖ్యల మొత్తం 20 మరియు వాటి భేదం 4. ఆ సంఖ్యలను కనుగొనండి.",
               "జాతిపితగా ఎవరిని పిలుస్తారు?", "సముద్ర మట్టం వద్ద నీరు 100 డిగ్రీల సెల్సియస్ వద్ద మరుగుతుంది.",
               "కింది వాటిలో సరైన ఎంపికను ఎంచుకోండి."],
    "Urdu": ["بھارت کا دارالحکومت کیا ہے؟", "بھارت کا سب سے لمبا دریا کون سا ہے؟",
             "دو اعداد کا مجموعہ 20 ہے اور ان کا فرق 4 ہے۔ اعداد معلوم کیجیے۔",
             "بابائے قوم کے نام سے کسے جانا جاتا ہے؟", "سطح سمندر پر پانی 100 ڈگری سیلسیس پر ابلتا ہے۔",
             "درج ذیل میں سے درست آپشن منتخب کیجیے۔"],
}

# share of words damaged per (language) for English source, Hindi source; None = no output for that direction
NOISE = {
    "Assamese": (0.05, 0.12), "Bengali": (0.10, 0.08), "Gujarati": (0.15, 0.20), "Kannada": (0.25, 0.30),
    "Konkani": (0.35, 0.30), "Malayalam": (0.08, 0.15), "Manipuri (Meitei)": (None, None),
    "Marathi": (0.12, 0.10), "Odia": (0.30, 0.40), "Punjabi": (0.18, 0.12), "Tamil": (0.40, 0.35),
    "Telugu": (0.06, 0.10), "Urdu": (0.22, None),
}
SKIP_ROWS = {("Odia", "English"): {"Q005"}}


def damage(text, p, rng):
    words = text.split(" ")
    out, i = [], 0
    while i < len(words):
        r = rng.random()
        if r < p / 2 and len(words) > 2:
            i += 1                                   # drop a word
        elif r < p and i + 1 < len(words):
            out += [words[i + 1], words[i]]          # swap with the next word
            i += 2
        else:
            out.append(words[i])
            i += 1
    return " ".join(out)


def write(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    write("1_source_questions.csv", ["id", "english", "hindi"], list(zip(IDS, ENGLISH, HINDI)))
    write("2_reference_translations.csv", ["id"] + ev.LANGUAGES,
          [[IDS[k]] + [REFS[lang][k] for lang in ev.LANGUAGES] for k in range(len(IDS))])

    rng = random.Random(7)
    rows = []
    for lang in ev.LANGUAGES:
        for s, p in zip(ev.SOURCES, NOISE[lang]):
            if p is None:
                continue
            for k, qid in enumerate(IDS):
                if qid in SKIP_ROWS.get((lang, s), set()):
                    continue
                rows.append([qid, s, lang, damage(REFS[lang][k], p, rng)])
    write("3_vendor_output.csv", ["id", "source_lang", "target_lang", "translation"], rows)
    print(f"Wrote 3 files to {OUT}  ({len(IDS)} questions, {len(rows)} vendor rows)")


if __name__ == "__main__":
    main()
