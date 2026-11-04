"""
Builds DUMMY input files in sample_data/ so the app can be tried without real data.
Every question is a multiple-choice question: the question and its four options (A) to (D) sit in ONE cell,
one per line.

  1_source_questions.csv        id, english, hindi
  2_reference_translations.csv  id + 13 language columns (placeholder text, NOT checked by native speakers)
  3_vendor_output.csv           id, source_lang, target_lang, translation
                                (the reference with some words dropped/swapped and some options replaced;
                                 NOT a real vendor's output)

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
LABELS = "ABCD"

# ---- question stems: capital, prime number, sum and difference, boiling point, multiplication, formula of water
STEMS = {
    "English": [
        "What is the capital of India?",
        "Which of the following is a prime number?",
        "The sum of two numbers is 20 and their difference is 4. Find the numbers.",
        "At what temperature does water boil at sea level?",
        "What is the value of 12 × 5?",
        "What is the chemical formula of water?",
    ],
    "Hindi": [
        "भारत की राजधानी क्या है?",
        "निम्नलिखित में से कौन-सी अभाज्य संख्या है?",
        "दो संख्याओं का योग 20 है और उनका अंतर 4 है। संख्याएँ ज्ञात कीजिए।",
        "समुद्र तल पर पानी किस तापमान पर उबलता है?",
        "12 × 5 का मान क्या है?",
        "पानी का रासायनिक सूत्र क्या है?",
    ],
    "Assamese": [
        "ভাৰতৰ ৰাজধানী কি?", "তলত দিয়াবোৰৰ ভিতৰত কোনটো মৌলিক সংখ্যা?",
        "দুটা সংখ্যাৰ যোগফল 20 আৰু ইহঁতৰ পাৰ্থক্য 4। সংখ্যা দুটা উলিওৱা।",
        "সাগৰ পৃষ্ঠত পানী কিমান উষ্ণতাত উতলে?", "12 × 5 ৰ মান কিমান?", "পানীৰ ৰাসায়নিক সূত্ৰ কি?"],
    "Bengali": [
        "ভারতের রাজধানী কী?", "নিচের কোনটি মৌলিক সংখ্যা?",
        "দুটি সংখ্যার যোগফল 20 এবং তাদের বিয়োগফল 4। সংখ্যা দুটি নির্ণয় করো।",
        "সমুদ্রপৃষ্ঠে জল কত তাপমাত্রায় ফোটে?", "12 × 5 এর মান কত?", "জলের রাসায়নিক সংকেত কী?"],
    "Gujarati": [
        "ભારતની રાજધાની કઈ છે?", "નીચેનામાંથી કઈ અવિભાજ્ય સંખ્યા છે?",
        "બે સંખ્યાઓનો સરવાળો 20 છે અને તેમનો તફાવત 4 છે. સંખ્યાઓ શોધો.",
        "દરિયાની સપાટીએ પાણી કેટલા તાપમાને ઉકળે છે?", "12 × 5 ની કિંમત કેટલી છે?", "પાણીનું રાસાયણિક સૂત્ર શું છે?"],
    "Kannada": [
        "ಭಾರತದ ರಾಜಧಾನಿ ಯಾವುದು?", "ಕೆಳಗಿನವುಗಳಲ್ಲಿ ಯಾವುದು ಅವಿಭಾಜ್ಯ ಸಂಖ್ಯೆ?",
        "ಎರಡು ಸಂಖ್ಯೆಗಳ ಮೊತ್ತ 20 ಮತ್ತು ಅವುಗಳ ವ್ಯತ್ಯಾಸ 4. ಆ ಸಂಖ್ಯೆಗಳನ್ನು ಕಂಡುಹಿಡಿಯಿರಿ.",
        "ಸಮುದ್ರ ಮಟ್ಟದಲ್ಲಿ ನೀರು ಯಾವ ತಾಪಮಾನದಲ್ಲಿ ಕುದಿಯುತ್ತದೆ?", "12 × 5 ರ ಬೆಲೆ ಎಷ್ಟು?",
        "ನೀರಿನ ರಾಸಾಯನಿಕ ಸೂತ್ರ ಯಾವುದು?"],
    "Konkani": [
        "भारताची राजधानी खंयची?", "सकयल दिल्ल्यांतली खंयची अविभाज्य संख्या?",
        "दोन संख्यांची बेरीज 20 आनी तांचो फरक 4. त्या संख्या सोदून काडात.",
        "दर्याच्या सपाटेर उदक कितल्या तापमानाक उकळटा?", "12 × 5 ची किंमत कितली?",
        "उदकाचें रासायनिक सूत्र कितें?"],
    "Malayalam": [
        "ഇന്ത്യയുടെ തലസ്ഥാനം ഏതാണ്?", "ചുവടെ നൽകിയവയിൽ ഏതാണ് അഭാജ്യസംഖ്യ?",
        "രണ്ട് സംഖ്യകളുടെ തുക 20 ഉം വ്യത്യാസം 4 ഉം ആണ്. സംഖ്യകൾ കണ്ടെത്തുക.",
        "സമുദ്രനിരപ്പിൽ വെള്ളം ഏത് താപനിലയിലാണ് തിളയ്ക്കുന്നത്?", "12 × 5 ന്റെ വില എത്രയാണ്?",
        "വെള്ളത്തിന്റെ രാസസൂത്രം എന്താണ്?"],
    "Manipuri (Meitei)": [
        "ꯏꯟꯗꯤꯌꯥꯒꯤ ꯔꯥꯖꯙꯥꯅꯤ ꯀꯔꯤꯅꯣ?", "ꯃꯈꯥꯗꯥ ꯌꯥꯕꯤꯔꯤꯕꯥ ꯃꯅꯨꯡꯗꯒꯤ ꯀꯗꯥꯏꯅꯣ ꯄ꯭ꯔꯥꯏꯝ ꯅꯝꯕꯔꯅꯣ?",
        "ꯃꯁꯤꯡ ꯑꯅꯤꯒꯤ ꯁꯔꯨꯛ 20 ꯑꯣꯏꯅꯤ ꯑꯃꯁꯨꯡ ꯃꯈꯥꯒꯤ ꯈꯟꯅꯕꯥ 4 ꯑꯣꯏꯅꯤ꯫ ꯃꯁꯤꯡ ꯑꯗꯨ ꯊꯤꯕꯤꯌꯨ꯫",
        "ꯁꯃꯨꯗ꯭ꯔꯒꯤ ꯃꯈꯥꯗꯥ ꯏꯁꯤꯡ ꯀꯌꯥ ꯑꯣꯏꯕꯥ ꯇꯦꯝꯄꯔꯦꯆꯔꯗꯥ ꯊꯥꯗꯣꯛꯀꯅꯣ?", "12 × 5 ꯒꯤ ꯃꯃꯜ ꯀꯌꯥꯅꯣ?",
        "ꯏꯁꯤꯡꯒꯤ ꯀꯦꯃꯤꯀꯦꯜ ꯐꯣꯔꯃꯨꯂꯥ ꯀꯔꯤꯅꯣ?"],
    "Marathi": [
        "भारताची राजधानी कोणती?", "खालीलपैकी कोणती मूळ संख्या आहे?",
        "दोन संख्यांची बेरीज 20 आहे आणि त्यांचा फरक 4 आहे. त्या संख्या शोधा.",
        "समुद्रसपाटीवर पाणी कोणत्या तापमानाला उकळते?", "12 × 5 ची किंमत किती आहे?", "पाण्याचे रासायनिक सूत्र कोणते?"],
    "Odia": [
        "ଭାରତର ରାଜଧାନୀ କେଉଁଟି?", "ନିମ୍ନଲିଖିତ ମଧ୍ୟରୁ କେଉଁଟି ମୌଳିକ ସଂଖ୍ୟା?",
        "ଦୁଇଟି ସଂଖ୍ୟାର ସମଷ୍ଟି 20 ଏବଂ ସେମାନଙ୍କ ଅନ୍ତର 4। ସଂଖ୍ୟା ଦୁଇଟି ନିର୍ଣ୍ଣୟ କର।",
        "ସମୁଦ୍ର ପୃଷ୍ଠରେ ପାଣି କେତେ ତାପମାତ୍ରାରେ ଫୁଟେ?", "12 × 5 ର ମୂଲ୍ୟ କେତେ?", "ଜଳର ରାସାୟନିକ ସୂତ୍ର କ'ଣ?"],
    "Punjabi": [
        "ਭਾਰਤ ਦੀ ਰਾਜਧਾਨੀ ਕਿਹੜੀ ਹੈ?", "ਹੇਠ ਲਿਖਿਆਂ ਵਿੱਚੋਂ ਕਿਹੜੀ ਅਭਾਜ ਸੰਖਿਆ ਹੈ?",
        "ਦੋ ਸੰਖਿਆਵਾਂ ਦਾ ਜੋੜ 20 ਹੈ ਅਤੇ ਉਨ੍ਹਾਂ ਦਾ ਅੰਤਰ 4 ਹੈ। ਸੰਖਿਆਵਾਂ ਪਤਾ ਕਰੋ।",
        "ਸਮੁੰਦਰ ਤਲ ਉੱਤੇ ਪਾਣੀ ਕਿੰਨੇ ਤਾਪਮਾਨ ਉੱਤੇ ਉੱਬਲਦਾ ਹੈ?", "12 × 5 ਦਾ ਮੁੱਲ ਕੀ ਹੈ?",
        "ਪਾਣੀ ਦਾ ਰਸਾਇਣਕ ਫਾਰਮੂਲਾ ਕੀ ਹੈ?"],
    "Tamil": [
        "இந்தியாவின் தலைநகரம் எது?", "பின்வருவனவற்றில் எது பகா எண்?",
        "இரண்டு எண்களின் கூட்டுத்தொகை 20 மற்றும் அவற்றின் வித்தியாசம் 4. அந்த எண்களைக் கண்டுபிடிக்கவும்.",
        "கடல் மட்டத்தில் தண்ணீர் எந்த வெப்பநிலையில் கொதிக்கிறது?", "12 × 5 இன் மதிப்பு என்ன?",
        "தண்ணீரின் வேதியியல் வாய்ப்பாடு என்ன?"],
    "Telugu": [
        "భారతదేశ రాజధాని ఏది?", "కింది వాటిలో ఏది ప్రధాన సంఖ్య?",
        "రెండు సంఖ్యల మొత్తం 20 మరియు వాటి భేదం 4. ఆ సంఖ్యలను కనుగొనండి.",
        "సముద్ర మట్టం వద్ద నీరు ఏ ఉష్ణోగ్రత వద్ద మరుగుతుంది?", "12 × 5 విలువ ఎంత?", "నీటి రసాయన సూత్రం ఏమిటి?"],
    "Urdu": [
        "بھارت کا دارالحکومت کیا ہے؟", "درج ذیل میں سے کون سا مفرد عدد ہے؟",
        "دو اعداد کا مجموعہ 20 ہے اور ان کا فرق 4 ہے۔ اعداد معلوم کیجیے۔",
        "سطح سمندر پر پانی کس درجہ حرارت پر ابلتا ہے؟", "12 × 5 کی قیمت کیا ہے؟", "پانی کا کیمیائی فارمولا کیا ہے؟"],
}

# ---- options. Q001 has text options (Mumbai, New Delhi, Kolkata, Chennai); Q003 pairs use the word "and"
CITIES = {
    "English": ["Mumbai", "New Delhi", "Kolkata", "Chennai"],
    "Hindi": ["मुंबई", "नई दिल्ली", "कोलकाता", "चेन्नई"],
    "Assamese": ["মুম্বাই", "নতুন দিল্লী", "কলকাতা", "চেন্নাই"],
    "Bengali": ["মুম্বাই", "নয়াদিল্লি", "কলকাতা", "চেন্নাই"],
    "Gujarati": ["મુંબઈ", "નવી દિલ્હી", "કોલકાતા", "ચેન્નઈ"],
    "Kannada": ["ಮುಂಬೈ", "ನವದೆಹಲಿ", "ಕೋಲ್ಕತ್ತಾ", "ಚೆನ್ನೈ"],
    "Konkani": ["मुंबय", "नवी दिल्ली", "कोलकाता", "चेन्नै"],
    "Malayalam": ["മുംബൈ", "ന്യൂഡൽഹി", "കൊൽക്കത്ത", "ചെന്നൈ"],
    "Manipuri (Meitei)": ["ꯃꯨꯝꯕꯥꯏ", "ꯅꯤꯎ ꯗꯦꯜꯍꯤ", "ꯀꯣꯂꯀꯥꯇꯥ", "ꯆꯦꯟꯅꯥꯏ"],
    "Marathi": ["मुंबई", "नवी दिल्ली", "कोलकाता", "चेन्नई"],
    "Odia": ["ମୁମ୍ବାଇ", "ନୂଆଦିଲ୍ଲୀ", "କୋଲକାତା", "ଚେନ୍ନାଇ"],
    "Punjabi": ["ਮੁੰਬਈ", "ਨਵੀਂ ਦਿੱਲੀ", "ਕੋਲਕਾਤਾ", "ਚੇਨਈ"],
    "Tamil": ["மும்பை", "புது தில்லி", "கொல்கத்தா", "சென்னை"],
    "Telugu": ["ముంబై", "న్యూ ఢిల్లీ", "కోల్కతా", "చెన్నై"],
    "Urdu": ["ممبئی", "نئی دہلی", "کولکاتا", "چنئی"],
}
AND = {"English": "and", "Hindi": "और", "Assamese": "আৰু", "Bengali": "এবং", "Gujarati": "અને", "Kannada": "ಮತ್ತು",
       "Konkani": "आनी", "Malayalam": "ഉം", "Manipuri (Meitei)": "ꯑꯃꯁꯨꯡ", "Marathi": "आणि", "Odia": "ଏବଂ",
       "Punjabi": "ਅਤੇ", "Tamil": "மற்றும்", "Telugu": "మరియు", "Urdu": "اور"}
PAIRS = [(6, 14), (8, 12), (9, 11), (10, 10)]


def options(q, lang):
    if q == 0:
        return CITIES[lang]
    if q == 2:
        if lang == "Malayalam":                                  # Malayalam joins with a suffix: "6 ഉം 14 ഉം"
            return [f"{a} {AND[lang]} {b} {AND[lang]}" for a, b in PAIRS]
        return [f"{a} {AND[lang]} {b}" for a, b in PAIRS]
    return {1: ["4", "6", "7", "9"],
            3: ["50 °C", "100 °C", "150 °C", "200 °C"],
            4: ["50", "60", "65", "70"],
            5: ["H2O", "CO2", "O2", "NaCl"]}[q]


def question(lang, q):
    """Question and its four options in one cell, one per line: stem, (A) .., (B) .., (C) .., (D) .."""
    lines = [STEMS[lang][q]] + [f"({LABELS[i]}) {o}" for i, o in enumerate(options(q, lang))]
    return "\n".join(lines)


# share of words damaged per language for English source, Hindi source; None = no output for that direction
NOISE = {
    "Assamese": (0.10, 0.20), "Bengali": (0.20, 0.15), "Gujarati": (0.30, 0.35), "Kannada": (0.45, 0.50),
    "Konkani": (0.60, 0.55), "Malayalam": (0.15, 0.25), "Manipuri (Meitei)": (None, None),
    "Marathi": (0.25, 0.20), "Odia": (0.55, 0.70), "Punjabi": (0.35, 0.25), "Tamil": (0.75, 0.65),
    "Telugu": (0.12, 0.18), "Urdu": (0.40, None),
}
SKIP_ROWS = {("Odia", "English"): {"Q005"}}


def damage_words(words, p, rng):
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
    return out


def damage(text, p, rng):
    """Damages the stem by dropping/swapping words. An option keeps its (A)..(D) label; a one-word option is
    sometimes replaced by another option's text, as a translation error would."""
    lines = text.split("\n")
    contents = [ln.split(" ", 1)[1] for ln in lines[1:]]
    out = [" ".join(damage_words(lines[0].split(" "), p, rng))]
    for ln in lines[1:]:
        label, content = ln.split(" ", 1)
        words = content.split(" ")
        if len(words) > 1:
            content = " ".join(damage_words(words, p, rng))
        elif rng.random() < p / 3:
            content = rng.choice([c for c in contents if c != content])
        out.append(f"{label} {content}")
    return "\n".join(out)


def write(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    n = len(IDS)
    write("1_source_questions.csv", ["id", "english", "hindi"],
          [[IDS[k], question("English", k), question("Hindi", k)] for k in range(n)])
    write("2_reference_translations.csv", ["id"] + ev.LANGUAGES,
          [[IDS[k]] + [question(lang, k) for lang in ev.LANGUAGES] for k in range(n)])

    rng = random.Random(7)
    rows = []
    for lang in ev.LANGUAGES:
        for s, p in zip(ev.SOURCES, NOISE[lang]):
            if p is None:
                continue
            for k, qid in enumerate(IDS):
                if qid in SKIP_ROWS.get((lang, s), set()):
                    continue
                rows.append([qid, s, lang, damage(question(lang, k), p, rng)])
    write("3_vendor_output.csv", ["id", "source_lang", "target_lang", "translation"], rows)
    print(f"Wrote 3 files to {OUT}  ({n} questions, {len(rows)} vendor rows)")


if __name__ == "__main__":
    main()
