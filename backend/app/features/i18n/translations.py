"""All user-facing text, per supported conversation language. The database/session's
canonical answer values stay in English regardless of language (see extraction/prompts.py
and conversation/fields.py) - this module only governs what the assistant shows/says."""

SUPPORTED_LANGUAGES = ("en", "hi", "mr")
DEFAULT_LANGUAGE = "en"

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "mr": "Marathi"}


def normalize_language(language: str | None) -> str:
    if language in SUPPORTED_LANGUAGES:
        return language
    return DEFAULT_LANGUAGE


# field_key -> {lang: (label, question)}
FIELD_TEXT: dict[str, dict[str, tuple[str, str]]] = {
    "company_name": {
        "en": ("Company Name", "What is the company name?"),
        "hi": ("कंपनी का नाम", "कंपनी का नाम क्या है?"),
        "mr": ("कंपनीचे नाव", "कंपनीचे नाव काय आहे?"),
    },
    "vehicle_number": {
        "en": ("Vehicle Number", "What is the vehicle number?"),
        "hi": ("वाहन नंबर", "वाहन नंबर क्या है?"),
        "mr": ("वाहन क्रमांक", "वाहन क्रमांक काय आहे?"),
    },
    "brand": {
        "en": ("Brand", "What is the brand?"),
        "hi": ("ब्रांड", "ब्रांड क्या है?"),
        "mr": ("ब्रँड", "ब्रँड काय आहे?"),
    },
    "container_number": {
        "en": ("Container Number", "What is the container number?"),
        "hi": ("कंटेनर नंबर", "कंटेनर नंबर क्या है?"),
        "mr": ("कंटेनर क्रमांक", "कंटेनर क्रमांक काय आहे?"),
    },
    "line_supervisor_name": {
        "en": ("Line Supervisor Name", "What is the line supervisor's name?"),
        "hi": ("लाइन सुपरवाइज़र का नाम", "लाइन सुपरवाइज़र का नाम क्या है?"),
        "mr": ("लाईन सुपरवायझरचे नाव", "लाईन सुपरवायझरचे नाव काय आहे?"),
    },
    "weight": {
        "en": ("Weight", "What is the weight, in kilograms?"),
        "hi": ("वज़न", "वज़न कितने किलोग्राम है?"),
        "mr": ("वजन", "वजन किती किलो आहे?"),
    },
    "four_hand": {
        "en": ("Four-Hand Quantity", "What is the four-hand quantity?"),
        "hi": ("फोर-हैंड मात्रा", "फोर-हैंड की मात्रा कितनी है?"),
        "mr": ("चार हँडचे प्रमाण", "चार हँडचे प्रमाण किती आहे?"),
    },
    "five_hand": {
        "en": ("Five-Hand Quantity", "What is the five-hand quantity?"),
        "hi": ("फाइव-हैंड मात्रा", "फाइव-हैंड की मात्रा कितनी है?"),
        "mr": ("पाच हँडचे प्रमाण", "पाच हँडचे प्रमाण किती आहे?"),
    },
    "six_hand": {
        "en": ("Six-Hand Quantity", "What is the six-hand quantity?"),
        "hi": ("सिक्स-हैंड मात्रा", "सिक्स-हैंड की मात्रा कितनी है?"),
        "mr": ("सहा हँडचे प्रमाण", "सहा हँडचे प्रमाण किती आहे?"),
    },
    "eight_hand": {
        "en": ("Eight-Hand Quantity", "What is the eight-hand quantity?"),
        "hi": ("एट-हैंड मात्रा", "एट-हैंड की मात्रा कितनी है?"),
        "mr": ("आठ हँडचे प्रमाण", "आठ हँडचे प्रमाण किती आहे?"),
    },
    "cluster": {
        "en": ("Cluster Quantity", "What is the cluster quantity?"),
        "hi": ("क्लस्टर मात्रा", "क्लस्टर की मात्रा कितनी है?"),
        "mr": ("क्लस्टरचे प्रमाण", "क्लस्टरचे प्रमाण किती आहे?"),
    },
    "labor_name": {
        "en": ("Labor Name", "What is the labor name?"),
        "hi": ("मजदूर का नाम", "मजदूर का नाम क्या है?"),
        "mr": ("मजुराचे नाव", "मजुराचे नाव काय आहे?"),
    },
    "driver_name": {
        "en": ("Driver Name", "What is the driver's name?"),
        "hi": ("ड्राइवर का नाम", "ड्राइवर का नाम क्या है?"),
        "mr": ("चालकाचे नाव", "चालकाचे नाव काय आहे?"),
    },
    "cold_storage_name": {
        "en": ("Cold Storage Name", "What is the cold storage name?"),
        "hi": ("कोल्ड स्टोरेज का नाम", "कोल्ड स्टोरेज का नाम क्या है?"),
        "mr": ("कोल्ड स्टोरेजचे नाव", "कोल्ड स्टोरेजचे नाव काय आहे?"),
    },
    "cold_storage_supervisor_name": {
        "en": ("Cold Storage Supervisor Name", "What is the cold storage supervisor's name?"),
        "hi": ("कोल्ड स्टोरेज सुपरवाइज़र का नाम", "कोल्ड स्टोरेज सुपरवाइज़र का नाम क्या है?"),
        "mr": ("कोल्ड स्टोरेज सुपरवायझरचे नाव", "कोल्ड स्टोरेज सुपरवायझरचे नाव काय आहे?"),
    },
    "vehicle_in_time": {
        "en": ("Vehicle In Time", "What is the vehicle in time? Please specify AM or PM."),
        "hi": ("वाहन अंदर आने का समय", "वाहन अंदर आने का समय क्या है? कृपया AM या PM बताएं।"),
        "mr": ("वाहन आत येण्याची वेळ", "वाहन आत येण्याची वेळ काय आहे? कृपया AM किंवा PM सांगा."),
    },
    "vehicle_out_time": {
        "en": ("Vehicle Out Time", "What is the vehicle out time? Please specify AM or PM."),
        "hi": ("वाहन बाहर जाने का समय", "वाहन बाहर जाने का समय क्या है? कृपया AM या PM बताएं।"),
        "mr": ("वाहन बाहेर जाण्याची वेळ", "वाहन बाहेर जाण्याची वेळ काय आहे? कृपया AM किंवा PM सांगा."),
    },
    "unloading_time": {
        "en": ("Unloading Time", "What is the unloading time? Please specify AM or PM."),
        "hi": ("उतराई का समय", "उतराई का समय क्या है? कृपया AM या PM बताएं।"),
        "mr": ("उतराईची वेळ", "उतराईची वेळ काय आहे? कृपया AM किंवा PM सांगा."),
    },
}

# Canonical (English) section title -> localized title
SECTION_TEXT: dict[str, dict[str, str]] = {
    "Company & Vehicle Details": {
        "en": "Company & Vehicle Details",
        "hi": "कंपनी और वाहन विवरण",
        "mr": "कंपनी आणि वाहनाची माहिती",
    },
    "Banana Hand & Cluster Quantities": {
        "en": "Banana Hand & Cluster Quantities",
        "hi": "केले के हाथ और क्लस्टर मात्रा",
        "mr": "केळीच्या हँड आणि क्लस्टरचे प्रमाण",
    },
    "Additional Information": {
        "en": "Additional Information",
        "hi": "अतिरिक्त जानकारी",
        "mr": "अतिरिक्त माहिती",
    },
}

TOTAL_LABEL = {"en": "Total Quantity", "hi": "कुल मात्रा", "mr": "एकूण प्रमाण"}

UI_TEXT: dict[str, dict[str, str]] = {
    "intro": {
        "en": "Please answer the following questions - you can type or record them all together:",
        "hi": "कृपया निम्नलिखित प्रश्नों के उत्तर दें - आप सभी उत्तर एक साथ टाइप या रिकॉर्ड कर सकते हैं:",
        "mr": "कृपया खालील प्रश्नांची उत्तरे द्या. तुम्ही सर्व प्रश्नांची उत्तरे एकत्र टाइप करू शकता किंवा बोलून रेकॉर्ड करू शकता.",
    },
    "still_need": {
        "en": "I still need a few things - please answer these together:",
        "hi": "मुझे अभी भी कुछ जानकारी चाहिए - कृपया ये उत्तर एक साथ दें:",
        "mr": "मला अजून काही माहिती हवी आहे - कृपया हे एकत्र उत्तर द्या:",
    },
    "confirm_header": {
        "en": "Please confirm the following details:",
        "hi": "कृपया निम्नलिखित विवरण की पुष्टि करें:",
        "mr": "कृपया खालील माहिती तपासून खात्री करा.",
    },
    "sorry_not_catch": {
        "en": "Sorry, I didn't catch that. {question}",
        "hi": "माफ़ कीजिए, मुझे समझ नहीं आया। {question}",
        "mr": "माफ करा, मला ते समजले नाही. {question}",
    },
    "sorry_try_again": {
        "en": "Sorry, I didn't catch that. Please try again.",
        "hi": "माफ़ कीजिए, मुझे समझ नहीं आया। कृपया फिर से प्रयास करें।",
        "mr": "माफ करा, मला ते समजले नाही. कृपया पुन्हा प्रयत्न करा.",
    },
    "unclear": {
        "en": "I couldn't understand that clearly. {question}",
        "hi": "मुझे यह स्पष्ट रूप से समझ नहीं आया। {question}",
        "mr": "मला ते नीट समजले नाही. {question}",
    },
    "could_not_tell_field": {
        "en": "I couldn't tell which field you meant. Please say which field to correct and its new value.",
        "hi": "मुझे यह समझ नहीं आया कि आप कौन सा फ़ील्ड ठीक करना चाहते हैं। कृपया बताएं कि कौन सा फ़ील्ड ठीक करना है और उसका नया मूल्य।",
        "mr": "तुम्ही कोणते फील्ड सुधारायचे आहे ते मला समजले नाही. कृपया कोणते फील्ड आणि नवीन मूल्य सांगा.",
    },
    "new_value_unclear": {
        "en": "I couldn't understand the new value clearly. {question}",
        "hi": "मुझे नया मूल्य स्पष्ट रूप से समझ नहीं आया। {question}",
        "mr": "मला नवीन मूल्य नीट समजले नाही. {question}",
    },
}

# Field-specific validation message templates. {label} substitutes the localized field label.
VALIDATION_TEXT: dict[str, dict[str, str]] = {
    "required": {
        "en": "{label} is required",
        "hi": "{label} आवश्यक है",
        "mr": "{label} आवश्यक आहे",
    },
    "max_length": {
        "en": "{label} must be {max} characters or fewer",
        "hi": "{label} अधिकतम {max} अक्षरों का होना चाहिए",
        "mr": "{label} जास्तीत जास्त {max} अक्षरांचे असावे",
    },
    "must_be_one_of": {
        "en": "{label} must be one of: {options}",
        "hi": "{label} इनमें से एक होना चाहिए: {options}",
        "mr": "{label} यापैकी एक असावे: {options}",
    },
    "must_be_number": {
        "en": "{label} must be a number",
        "hi": "{label} एक संख्या होनी चाहिए",
        "mr": "{label} एक संख्या असावी",
    },
    "must_be_at_least": {
        "en": "{label} must be at least {min}",
        "hi": "{label} कम से कम {min} होनी चाहिए",
        "mr": "{label} किमान {min} असावे",
    },
    "must_be_at_most": {
        "en": "{label} must be at most {max}",
        "hi": "{label} अधिकतम {max} होनी चाहिए",
        "mr": "{label} कमाल {max} असावे",
    },
    "vehicle_format": {
        "en": "{label} doesn't match a valid plate format (e.g. MH12AB1234)",
        "hi": "{label} मान्य नंबर प्लेट प्रारूप से मेल नहीं खाता (जैसे MH12AB1234)",
        "mr": "{label} वैध नंबर प्लेट स्वरूपाशी जुळत नाही (उदा. MH12AB1234)",
    },
    "time_format": {
        "en": "{label} must be in HH:MM 24-hour format",
        "hi": "{label} HH:MM (24-घंटे) प्रारूप में होना चाहिए",
        "mr": "{label} HH:MM (24-तास) स्वरूपात असावे",
    },
    "time_after": {
        "en": "{later} ({later_time}) must be after {earlier} ({earlier_time})",
        "hi": "{later} ({later_time}) को {earlier} ({earlier_time}) के बाद होना चाहिए",
        "mr": "{later} ({later_time}) हे {earlier} ({earlier_time}) नंतरचे असावे",
    },
}


def field_label(field_key: str, language: str) -> str:
    lang = normalize_language(language)
    return FIELD_TEXT[field_key][lang][0]


def field_question(field_key: str, language: str) -> str:
    lang = normalize_language(language)
    return FIELD_TEXT[field_key][lang][1]


def section_title(canonical_title: str, language: str) -> str:
    lang = normalize_language(language)
    return SECTION_TEXT[canonical_title][lang]


def total_label(language: str) -> str:
    return TOTAL_LABEL[normalize_language(language)]


def ui_text(key: str, language: str, **kwargs) -> str:
    template = UI_TEXT[key][normalize_language(language)]
    return template.format(**kwargs) if kwargs else template


def validation_text(key: str, language: str, **kwargs) -> str:
    template = VALIDATION_TEXT[key][normalize_language(language)]
    return template.format(**kwargs)
