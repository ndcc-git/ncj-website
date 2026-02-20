import itertools

from flask import json
from pymongo import MongoClient
import extensions


segments = [
    {
        "name": "সংগীত প্রতিযোগিতা",
        "img": "https://scontent.fdac138-1.fna.fbcdn.net/v/t39.30808-6/488936333_1081129804047863_8888396448186167548_n.jpg?_nc_cat=108&ccb=1-7&_nc_sid=13d280&_nc_ohc=iLTtMS7rvcwQ7kNvwE_7Pfh&_nc_oc=Adns9XO45Opzdmz1aRn32i6OyN1PygMX7bkZ5rYAE6rOGretcV-qI-y0wkE4oBErPFg&_nc_zt=23&_nc_ht=scontent.fdac138-1.fna&_nc_gid=H6vj5slipf2btPfpYwqqfQ&oh=00_AftP3UJFsi5HH6uA2d46xI_hMwonVvQCDm2kTvvt-_81LQ&oe=699CB71A",
        "info": "",
        "type": "Solo",
        "categories": [
            "P",
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "sub_categories": [
            "রবীন্দ্র সংগীত",
            "নজরুল সংগীত",
            "আধুনিক সংগীত",
            "লোকসংগীত",
            "দেশাত্মবোধক সংগীত",
            "উচ্চাঙ্গ সংগীত"
        ],
        "rules": [
            "প্রতিটি বিভাগ আলাদা ইভেন্ট হিসেবে গণ্য হবে।",
            "প্রতিযোগীরা সর্বোচ্চ ৩ মিনিট সময় পাবেন।"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "যন্ত্রসংগীত প্রতিযোগিতা",
        "img": "https://scontent.fdac138-2.fna.fbcdn.net/v/t39.30808-6/489738494_1081129434047900_7081320429063248130_n.jpg?_nc_cat=101&ccb=1-7&_nc_sid=13d280&_nc_ohc=0yEGw3nobHcQ7kNvwGRrEQH&_nc_oc=Adlss8zkpeViLQq8ZEq0_AGCoYttg7Saa3qOp4VN3ErUeul75078wd1_oFUCkPe6PBc&_nc_zt=23&_nc_ht=scontent.fdac138-2.fna&_nc_gid=xtJ0pps1WFwc4I_B8ilj5w&oh=00_AfsOVxghh8HSMyVVyyuaQIIgl4hwiQEgOU7Hgi3i3mlbeQ&oe=699C87F2",
        "info": "",
        "type": "Solo",
        "categories": [
            "P",
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "sub_categories": [
            "পারকাশন যন্ত্র / তাল যন্ত্র",
            "তারযুক্ত যন্ত্র / তার যন্ত্র",
            "মেলোডিক যন্ত্র / সুর যন্ত্র"
        ],
        "rules": [
            "সর্বোচ্চ সময়: 8 মিনিট",
            "নিজস্ব যন্ত্র সঙ্গে আনতে হবে।",
            "ইস্টার্ন ও ওয়েস্টার্ন যন্ত্র ব্যবহার করা যাবে (হারমোনিয়াম ব্যতীত)।"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "ব্যাটল অব দ্য ব্যান্ডস",
        "img": "https://scontent.fdac138-1.fna.fbcdn.net/v/t39.30808-6/488706976_1081131130714397_5589639071416878270_n.jpg?_nc_cat=110&ccb=1-7&_nc_sid=13d280&_nc_ohc=4QTS-3zzgfsQ7kNvwGrma9s&_nc_oc=Adm0vt9AykWwsGwMszaS2Htq1sQ9o8jSzsYKSR74nLT431GDr5qwcDL5dBpBAOdlJf0&_nc_zt=23&_nc_ht=scontent.fdac138-1.fna&_nc_gid=CYCVqvkm3EXtbozSaR80Tw&oh=00_Afv82p--qP76-5HmFlWIp_BzzFXXcFijFc0Nukr7LpwuEQ&oe=699CB83C",
        "info": "নটর ডেম কালচারাল ক্লাব আয়োজন করছে স্কুল ও কলেজ পর্যায়ের ব্যান্ডদের জন্য বিশেষ প্রতিযোগিতা।",
        "type": "Team",
        "categories": [],
        "is_free_for_all": True,
        "additional_points": [
            "স্কুল ও কলেজ পর্যায়ের ব্যান্ড অংশগ্রহণ করতে পারবে",
            "সেরা ৮টি ব্যান্ড ফাইনালে উঠবে",
            "নির্বাচিত ব্যান্ডকে ২০০০ টাকা এন্ট্রি ফি দিতে হবে",
            "জ্যামিং ভিডিও ও ট্র্যাকলিস্ট গুগল ড্রাইভে পাঠাতে হবে"
        ],
        "rules": [
            "কমপক্ষে ২টি গান পরিবেশন (২০ মিনিট)",
            "সদস্য সংখ্যা: ৩–৬ জন",
            "শুধুমাত্র বাংলা গান (সফট মেটাল ও রক)",
            "ড্রামস সরবরাহ করা হবে",
            "নিজস্ব গান অতিরিক্ত সুবিধা পাবে",
            "ধূমপান ও মাদক নিষিদ্ধ"
        ],
        "price": 0,
        "current_participants": 0
    },
    {
        "name": "বিটবক্স ব্রল",
        "img": "https://scontent.fdac138-2.fna.fbcdn.net/v/t39.30808-6/489054095_1081128510714659_360702231467706330_n.jpg?_nc_cat=102&ccb=1-7&_nc_sid=13d280&_nc_ohc=xuAnbI5jwsAQ7kNvwGchLKc&_nc_oc=Adl4jeBTEDF6mO_lyZ0rbiddAITWDT3vdeG31DjRB0nD8GxRZBqTkYGKH61HRW99VgA&_nc_zt=23&_nc_ht=scontent.fdac138-2.fna&_nc_gid=ASnP1PlDW1cWwd5GnGkIVA&oh=00_AfuWu09TSB6K3QEy0yqChIZMZkGr_L8rm99LDqN9BoHVYw&oe=699CB9CB",
        "info": "",
        "type": "Solo",
        "categories": [],
        "is_free_for_all": True,
        "rules": [
            "একক ইভেন্ট",
            "সময়: ৩–৪ মিনিট",
            "সেরা ৮ জন নিয়ে ফাইনাল",
            "গালিগালাজ নিষিদ্ধ",
            "বিচারকের সিদ্ধান্ত চূড়ান্ত"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "একক অভিনয়",
        "img": "https://scontent.fdac138-1.fna.fbcdn.net/v/t39.30808-6/489409345_1081128244048019_9112323006850544091_n.jpg?_nc_cat=108&ccb=1-7&_nc_sid=13d280&_nc_ohc=RTNwhPQxBSIQ7kNvwGAdEYV&_nc_oc=Adkbm7ujFauXRISe1verQLKLR9cOFqQBccpA27YPjjYT0pkCWN1v2JOGhbpRFUlPMIU&_nc_zt=23&_nc_ht=scontent.fdac138-1.fna&_nc_gid=MPw6x2sc12wscrSrc3w8pA&oh=00_AfsgTgoTaRkq-Un8BgWfMSmrDK0pb9XIz0NAKrIiGdjw0A&oe=699C88B2",
        "type": "Solo",
        "categories": [
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "rules": [
            "বিষয়: নিজের পছন্দ",
            "সময়: ৩ মিনিট",
            "গ্রিন রুম থাকবে"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "বইভিত্তিক কুইজ",
        "img": "https://scontent.fdac138-1.fna.fbcdn.net/v/t39.30808-6/489321654_1081130850714425_1952282943695779918_n.jpg?_nc_cat=110&ccb=1-7&_nc_sid=13d280&_nc_ohc=46vJ-tm2Bx0Q7kNvwH72EpM&_nc_oc=AdmSjOCQnithG6VvTNodLyE3t7MfMiOJ8azIzTD0kctzr1k5088zBBzESX6ci2yO5E4&_nc_zt=23&_nc_ht=scontent.fdac138-1.fna&_nc_gid=De6GML0P21NVxE4jx3QJ5w&oh=00_AftrPlYNTmPt1ED9qsX6K5P49IurN7XUR9VO3ZhoO7N6hg&oe=699CB0E2",
        "type": "Team",
        "categories": [
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "category_config": {
            "J": {
                "books": [
                    "পথের পাঁচালী - বিভূতিভূষণ বন্দ্যোপাধ্যায়",
                    "চাঁদের পাহাড় - বিভূতিভূষণ বন্দ্যোপাধ্যায়"
                ]
            },
            "S": {
                "books": [
                    "বরফ গলা নদী - জহির রায়হান",
                    "ওঙ্কার - আহমেদ ছফা"
                ]
            },
            "HS": {
                "books": [
                    "দুধে ভাতে উৎপাত - আখতারুজ্জামান ইলিয়াস",
                    "জোছনা ও জননীর গল্প - হুমায়ূন আহমেদ"
                ]
            }
        },
        "rules": [
            "দল: ৩ জন",
            "একটিমাত্র লিখিত রাউন্ড",
            "মোবাইল নিষিদ্ধ"
        ],
        "price": 200,
        "current_participants": 0
    },
    {
        "name": "কবিতা আবৃত্তি",
        "img": "https://scontent.fdac138-1.fna.fbcdn.net/v/t39.30808-6/488908568_1081131124047731_9081225032676603544_n.jpg?_nc_cat=100&ccb=1-7&_nc_sid=13d280&_nc_ohc=FMUZOuMct8QQ7kNvwH7YJFV&_nc_oc=AdkKOt_DlL51HP9IZJIKZCT7UsL-knidSs2zwbCYwdbb4hhyxeDaWZycLS_R--LaCiM&_nc_zt=23&_nc_ht=scontent.fdac138-1.fna&_nc_gid=MKBsAOdR8yUr3BV60YKoiQ&oh=00_AftP-Rkt26ZB9M-S4tJDLeSzKP_ltjNm-aLqLK2kD4FgbA&oe=699CAD40",
        "type": "Solo",
        "categories": [
            "P",
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "rules": [
            "বিষয়: উন্মুক্ত",
            "সময়: ২ মিনিট",
            "নিজস্ব কবিতা আবৃত্তি করা যাবে"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "চিত্রাঙ্কন প্রতিযোগিতা",
        "img": "https://scontent.fdac138-2.fna.fbcdn.net/v/t39.30808-6/489106317_1081129467381230_8270358021192672358_n.jpg?_nc_cat=105&ccb=1-7&_nc_sid=13d280&_nc_ohc=z2Fentte7BwQ7kNvwHpGR74&_nc_oc=AdmMJV5g2lA3nAnhwDy0n1ey8g0ckoLhiny6CITwgHRVl6-9kioeEiQbNh87gk6cNM0&_nc_zt=23&_nc_ht=scontent.fdac138-2.fna&_nc_gid=VV8VLNMkM_EcBbNO9dFVlw&oh=00_Afs2_5GWtD8nGGxSm2nfutgSFG--PUmqWLIb49e6-2J_7g&oe=699C826E",
        "type": "Solo",
        "categories": [
            "K",
            "P",
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "category_config": {
            "K": {
                "theme": "উন্মুক্ত"
            },
            "P": {
                "theme": "উন্মুক্ত"
            },
            "J": {
                "theme": "বাংলাদেশের নববর্ষ, গ্রীষ্মকাল"
            },
            "S": {
                "theme": "বাংলার ঐতিহ্য, গ্রামবাংলার জীবন ও প্রকৃতি"
            },
            "HS": {
                "theme": "লোকসংস্কৃতির নীরব মৃত্যু, বাংলাদেশের লোকজ সাংস্কৃতিক ঐতিহ্য"
            }
        },
        "rules": [
            "কাগজ প্রদান করা হবে",
            "অন্যান্য উপকরণ নিজে আনতে হবে"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "একক নৃত্য প্রতিযোগিতা",
        "img": "https://scontent.fdac138-2.fna.fbcdn.net/v/t39.30808-6/488622495_1081128687381308_3539647218296049529_n.jpg?_nc_cat=105&ccb=1-7&_nc_sid=13d280&_nc_ohc=htyNqvJsGzEQ7kNvwG_LYW_&_nc_oc=Adnv-D0i7Hlf63YbHnHoql04JDas3lL5zkzHEycbpPPQtYYeAAlIlSAVUqdCfLhSs3I&_nc_zt=23&_nc_ht=scontent.fdac138-2.fna&_nc_gid=OH_JYH4ymG4_JRtbDxyiTQ&oh=00_AfvKS2SarZwx6Osn1XZWo9jRhPDKCVkHsO63ml1XdapLbQ&oe=699C8234",
        "type": "Solo",
        "categories": [
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "sub_categories": [
            "শাস্ত্রীয় নৃত্য",
            "সৃজনশীল নৃত্য"
        ],
        "rules": [
            "অংশগ্রহণকারীরা শুধুমাত্র ঐতিহ্যবাহী নৃত্য পরিবেশন করতে পারবেন। কোনো প্রকার পাশ্চাত্য (Western) নৃত্য গ্রহণযোগ্য নয়।",
            "ব্যাকগ্রাউন্ড মিউজিক হিসেবে শুধুমাত্র বাংলা ও শাস্ত্রীয় গান ব্যবহার করা যাবে। ডিজে, হিপ-হপ বা অনুরূপ সঙ্গীত নিষিদ্ধ।",
            "একটি গ্রিন রুম প্রদান করা হবে। অংশগ্রহণকারীরা নিজেদের প্রয়োজনীয় পোশাক ও সামগ্রী সঙ্গে আনতে পারবেন।"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "দলীয় নৃত্য প্রতিযোগিতা",
        "img": "https://scontent.fdac138-2.fna.fbcdn.net/v/t39.30808-6/488997959_1081133150714195_6979599206959649111_n.jpg?_nc_cat=106&ccb=1-7&_nc_sid=13d280&_nc_ohc=DvlRXFYqYo8Q7kNvwHKqIs3&_nc_oc=AdkGnhVMaBKhV1rT4KH0MZkAZCaAdM-bpG4mrBsS3gMxDjIU0PSonsqKcwawYCysKGA&_nc_zt=23&_nc_ht=scontent.fdac138-2.fna&_nc_gid=6Rqb4RgG9oYJHlb4Lr5acw&oh=00_AftsWcbQ9zwKw1twtTuCFbQIJJyBankyC8If5Dx5pQ-moA&oe=699CABCA",
        "type": "Team",
        "categories": [
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "sub_categories": [
            "শাস্ত্রীয় নৃত্য",
            "সৃজনশীল নৃত্য"
        ],
        "rules": [
            "শুধুমাত্র দলীয় পরিবেশনা গ্রহণযোগ্য।",
            "অংশগ্রহণকারীরা কেবল ঐতিহ্যবাহী নৃত্য পরিবেশন করতে পারবেন। কোনো প্রকার পাশ্চাত্য নৃত্য অনুমোদিত নয়।",
            "ব্যাকগ্রাউন্ড মিউজিক হিসেবে শুধুমাত্র বাংলা ও শাস্ত্রীয় গান ব্যবহার করা যাবে। ডিজে, হিপ-হপ বা অনুরূপ সঙ্গীত নিষিদ্ধ।",
            "একটি গ্রিন রুম প্রদান করা হবে। অংশগ্রহণকারীরা প্রয়োজনীয় পোশাক সঙ্গে আনতে পারবেন।"
        ],
        "price": 300,
        "current_participants": 0
    },
    {
        "name": "হাতের লেখা প্রতিযোগিতা",
        "img": "https://static.vecteezy.com/system/resources/thumbnails/072/596/930/small/a-person-is-writing-on-a-piece-of-paper-with-a-pen-photo.jpeg",
        "type": "Solo",
        "categories": [
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "rules": [
            "একজন অংশগ্রহণকারী বাংলা ও ইংরেজি—উভয় হাতের লেখা প্রতিযোগিতায় অংশ নিতে পারবেন।",
            "নির্দিষ্ট একটি বিষয়ের ওপর প্রদত্ত অনুচ্ছেদ ৩০ মিনিটের মধ্যে লিখতে হবে (বিষয় তাৎক্ষণিকভাবে দেওয়া হবে)।"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "উপস্থিত বক্তৃতা প্রতিযোগিতা",
        "img": "https://scontent.fdac138-1.fna.fbcdn.net/v/t39.30808-6/488908568_1081131124047731_9081225032676603544_n.jpg?_nc_cat=100&ccb=1-7&_nc_sid=13d280&_nc_ohc=FMUZOuMct8QQ7kNvwH7YJFV&_nc_oc=AdkKOt_DlL51HP9IZJIKZCT7UsL-knidSs2zwbCYwdbb4hhyxeDaWZycLS_R--LaCiM&_nc_zt=23&_nc_ht=scontent.fdac138-1.fna&_nc_gid=MKBsAOdR8yUr3BV60YKoiQ&oh=00_AftP-Rkt26ZB9M-S4tJDLeSzKP_ltjNm-aLqLK2kD4FgbA&oe=699CAD40",
        "type": "Solo",
        "categories": [
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "rules": [
            "বক্তৃতা অবশ্যই বাংলায় দিতে হবে।",
            "অংশগ্রহণকারীরা বাছাইকরনের মাধ্যমে একটি বিষয় নির্বাচন করবেন।",
            "প্রয়োজনীয় পোশাক পরে অংশগ্রহণ করা যাবে।"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "দেয়ালিকা প্রতিযোগিতা",
        "img": "https://scontent.fdac138-1.fna.fbcdn.net/v/t39.30808-6/489455459_1081132550714255_2794359035305291148_n.jpg?_nc_cat=110&ccb=1-7&_nc_sid=13d280&_nc_ohc=CWrWKEt-HfIQ7kNvwHRm_8Y&_nc_oc=Adl4k4phnAaVFSdxR22mb4DHT9G91QpaloIG3s-CsqOQX2FAnIrX1W0K0gzhSZzNpY4&_nc_zt=23&_nc_ht=scontent.fdac138-1.fna&_nc_gid=9wFkH5SeqK8p9ofBPf8PQg&oh=00_Afs_xohbP3xowRm4jgr2tq1wi2lFE1JhnKg2qcYdw6OErA&oe=699CB349",
        "type": "Team",
        "categories": [
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "category_config": {
            "J": {
                "theme": "বাংলাদেশের উৎসব"
            },
            "S": {
                "theme": "বাংলার লোক গাঁথা"
            },
            "HS": {
                "theme": "বাংলার লোক গাঁথা"
            }
        },
        "rules": [
            "নির্ধারিত বিষয় অনুযায়ী একটি দেয়ালিকা তৈরি করতে হবে।",
            "একটি দলে ৩–৪ জন সদস্য থাকতে হবে।",
            "দলের সকল সদস্য একই শিক্ষাপ্রতিষ্ঠানের হতে হবে।",
            "দেয়ালিকা আকার সর্বোচ্চ ৫×৩ ফুটের মধ্যে সীমাবদ্ধ রাখতে হবে।",
            "প্রয়োজনীয় সকল উপকরণ (মাল্টি-প্লাগ, কাঁচি, আঠা ইত্যাদি) অংশগ্রহণকারীদের নিজ দায়িত্বে আনতে হবে।",
            "ইভেন্ট শিডিউল অনুযায়ী নির্ধারিত সময়ে দেয়ালিকা ম্প্রদর্শনের জন্য আনতে হবে।",
            "বিচার পর্বে দলের অন্তত একজন সদস্যকে উপস্থিত থেকে দেয়ালিকা ভাবনা ব্যাখ্যা করতে হবে, অন্যথায় দলটি বাতিল বলে গণ্য হতে পারে।"
        ],
        "price": 200,
        "current_participants": 0
    },
    {
        "name": "স্ক্র্যাপবুক প্রতিযোগিতা",
        "img": "https://scontent.fdac138-1.fna.fbcdn.net/v/t39.30808-6/489916462_1081128634047980_1103298756064657342_n.jpg?_nc_cat=110&ccb=1-7&_nc_sid=13d280&_nc_ohc=55bc87yMm2cQ7kNvwHBxFrg&_nc_oc=AdnnntTgo58kht1kDsBy_4stEuujcKfKbKWQGIWE06cjKhuzrEMyHC5Cll5lqKHUdMY&_nc_zt=23&_nc_ht=scontent.fdac138-1.fna&_nc_gid=k-iN8WIPLfytvsqRXba7Qg&oh=00_AfvQODjjBp3sd3ivHBvO8PlxNLbdbwQVXNquUX_M-3cTWA&oe=699CB361",
        "type": "Team",
        "categories": [
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "category_config": {
            "J": {
                "theme": "কাজী নজরুল ইসলাম"
            },
            "S": {
                "theme": "লালন সাঁই"
            },
            "HS": {
                "theme": "রবীন্দ্রনাথ ঠাকুর"
            }
        },
        "rules": [
            "প্রতিটি দল ২–৩ জন সদস্য নিয়ে গঠিত হতে হবে।",
            "অংশগ্রহণকারীদের উল্লিখিত বিষয়ের ওপর নিজেরাই একটি স্ক্র্যাপবুক তৈরি করতে হবে।",
            "সাবমিশনের তারিখ পরবর্তীতে জানানো হবে।"
        ],
        "price": 200,
        "current_participants": 0
    },
    {
        "name": "শুদ্ধপাঠ প্রতিযোগিতা",
        "img": "https://scontent.fdac138-1.fna.fbcdn.net/v/t39.30808-6/488908568_1081131124047731_9081225032676603544_n.jpg?_nc_cat=100&ccb=1-7&_nc_sid=13d280&_nc_ohc=FMUZOuMct8QQ7kNvwH7YJFV&_nc_oc=AdkKOt_DlL51HP9IZJIKZCT7UsL-knidSs2zwbCYwdbb4hhyxeDaWZycLS_R--LaCiM&_nc_zt=23&_nc_ht=scontent.fdac138-1.fna&_nc_gid=MKBsAOdR8yUr3BV60YKoiQ&oh=00_AftP-Rkt26ZB9M-S4tJDLeSzKP_ltjNm-aLqLK2kD4FgbA&oe=699CAD40",
        "type": "Solo",
        "categories": [
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "rules": [
            "অংশগ্রহণকারীদের একটি বাংলা গদ্যাংশ, কবিতা অথবা সংবাদাংশ পাঠ করতে বলা হবে।",
            "শুদ্ধ, প্রমিত ও সঠিক উচ্চারণ বাধ্যতামূলক।",
            "পাঠ অবশ্যই স্পষ্ট, শ্রুতিমধুর ও সাবলীল হতে হবে।",
            "অতিরিক্ত নাটকীয়তা বা উচ্চস্বরে চিৎকার করা যাবে না।",
            "মুখস্থ আবৃত্তি গ্রহণযোগ্য নয়; প্রদত্ত লেখা থেকেই পড়তে হবে।",
            "অন্য কারো সঙ্গে যোগাযোগ বা ইঙ্গিত গ্রহণ সম্পূর্ণ নিষিদ্ধ।",
            "মোবাইল ফোন বা যেকোনো ধরনের ইলেকট্রনিক ডিভাইস ব্যবহার সম্পূর্ণ নিষিদ্ধ।"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "মুভি–সিরিজ কুইজ প্রতিযোগিতা",
        "img": "https://scontent.fdac138-2.fna.fbcdn.net/v/t39.30808-6/488467781_1081129964047847_3230555714724769238_n.jpg?_nc_cat=103&ccb=1-7&_nc_sid=13d280&_nc_ohc=F7nnm880C2EQ7kNvwEVMXuY&_nc_oc=AdkP_avoItx1NKSlVK_nNK09WrJRUdYpcsf_fHC1AF6eTaMBzcnT9jx7RJiafvMfHuQ&_nc_zt=23&_nc_ht=scontent.fdac138-2.fna&_nc_gid=fNs2qnDsGgmflZIpHrdAEQ&oh=00_AftmIu-aEZ7kJFCDaheZB5dZBM-5inN9yN0OngSeKjPc5Q&oe=699CB028",
        "info": "চলচ্চিত্র ও টেলিভিশনের জাদুকরী জগৎ অন্বেষণ করুন এবং এমন এক রোমাঞ্চকর ভ্রমণে অংশ নিন, যেখানে রূপালি পর্দার মোহ মিশে যায় কুইজের উত্তেজনায়। চলচ্চিত্র, টিভি শো এবং বিনোদনের ইতিহাসে স্মরণীয় মুহূর্ত নিয়ে আপনার জ্ঞান যাচাই করুন—বর্তমান ও ক্লাসিক উভয় ধরনের সৃষ্টির ওপর গুরুত্ব দেওয়া হবে। আপনি একজন অভিজ্ঞ সিনেমাপ্রেমী হন বা সাধারণ দর্শক—এই কুইজ আপনাকে ভিজ্যুয়াল স্টোরিটেলিংয়ের শিল্পে এক উত্তেজনাপূর্ণ যাত্রার প্রতিশ্রুতি দেয়।",
        "type": "Team",
        "categories": [
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "category_config": {
            "S": {
                "movies": [
                    "আমার বন্ধু রাশেদ",
                    "Grave of the fireflies"
                ],
                "series": [
                    "Stranger things"
                ]
            },
            "HS": {
                "movies": [
                    "Parasite",
                    "রাইফেল রোটি আওরাত"
                ],
                "series": [
                    "Game of thrones"
                ]
            }
        },
        "rules": [
            "প্রতিটি দল ২–৩ জন সদস্য নিয়ে গঠিত হতে হবে।",
            "শুধুমাত্র একটি লিখিত রাউন্ড থাকবে।",
            "পরীক্ষার সময় স্মার্টফোন, ল্যাপটপ বা ট্যাবলেট ব্যবহার সম্পূর্ণ নিষিদ্ধ।"
        ],
        "price": 200,
        "current_participants": 0
    },
    {
        "name": "ফটোগ্রাফি প্রতিযোগিতা",
        "img": "https://i.postimg.cc/wjhvJgs9/Whats-App-Image-2026-02-20-at-4-01-55-PM.jpg",
        "type": "Submission",
        "categories": [],
        "is_free_for_all": True,
        "rules": [
            "এটি একটি অনলাইন সেগমেন্ট।",
            "ছবিতে দেশের যেকোনো অংশের সংস্কৃতির কোনো দিক ফুটে উঠতে হবে।",
            "শুধুমাত্র অংশগ্রহণকারীর নিজস্ব তোলা মৌলিক ছবি গ্রহণযোগ্য। কোনো ধরনের প্লেজারিজম বা বেসিক এডিটিং ছাড়া অতিরিক্ত ডিজিটাল ম্যানিপুলেশন করা যাবে না।",
            "ছবিতে সাংস্কৃতিক সংবেদনশীলতা বজায় রাখতে হবে এবং কোনো আপত্তিকর বা অনুচিত কনটেন্ট থাকা যাবে না।",
            "অনলাইন সাবমিশনের মাধ্যমে উচ্চ রেজোলিউশনের JPEG বা PNG ফরম্যাটের ছবি গ্রহণ করা হবে।"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "অ্যানিমে কুইজ প্রতিযোগিতা",
        "img": "https://scontent.fdac138-2.fna.fbcdn.net/v/t39.30808-6/488467781_1081129964047847_3230555714724769238_n.jpg?_nc_cat=103&ccb=1-7&_nc_sid=13d280&_nc_ohc=F7nnm880C2EQ7kNvwEVMXuY&_nc_oc=AdkP_avoItx1NKSlVK_nNK09WrJRUdYpcsf_fHC1AF6eTaMBzcnT9jx7RJiafvMfHuQ&_nc_zt=23&_nc_ht=scontent.fdac138-2.fna&_nc_gid=fNs2qnDsGgmflZIpHrdAEQ&oh=00_AftmIu-aEZ7kJFCDaheZB5dZBM-5inN9yN0OngSeKjPc5Q&oe=699CB028",
        "type": "Team",
        "categories": [
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "category_config": {
            "J": {
                "anime": [
                    "Spirited Away",
                    "Pokémon Original league",
                    "Arrietty"
                ]
            },
            "S": {
                "anime": [
                    "Demon Slayer",
                    "Death Note",
                    "My Hero Academia"
                ]
            },
            "HS": {
                "anime": [
                    "Naruto And Naruto Shippuden",
                    "Attack on Titan",
                    "Code geass"
                ]
            }
        },
        "rules": [
            "প্রতিটি দল ২ জন সদস্য নিয়ে গঠিত হতে হবে।",
            "শুধুমাত্র একটি লিখিত রাউন্ড থাকবে।",
            "পরীক্ষার সময় মোবাইল ফোন, ল্যাপটপ বা ট্যাবলেট ব্যবহার সম্পূর্ণ নিষিদ্ধ।"
        ],
        "price": 200,
        "current_participants": 0
    },
    {
        "name": "পপ কালচারাল কুইজ প্রতিযোগিতা",
        "img": "https://scontent.fdac138-2.fna.fbcdn.net/v/t39.30808-6/488467781_1081129964047847_3230555714724769238_n.jpg?_nc_cat=103&ccb=1-7&_nc_sid=13d280&_nc_ohc=F7nnm880C2EQ7kNvwEVMXuY&_nc_oc=AdkP_avoItx1NKSlVK_nNK09WrJRUdYpcsf_fHC1AF6eTaMBzcnT9jx7RJiafvMfHuQ&_nc_zt=23&_nc_ht=scontent.fdac138-2.fna&_nc_gid=tzS1FwNQ4HBgsQwMkg7oVQ&oh=00_AftymCW7cf-g89tjxM1J0Ch06_Z3-IKtO9UPgNtlVN5E5A&oe=699CB028",
        "type": "Solo",
        "categories": [
            "HS"
        ],
        "is_free_for_all": False,
        "rules": [
            "এটি একটি একক সেগমেন্ট।",
            "প্রতিযোগিতা নির্দিষ্ট সময়ের মধ্যে শেষ করতে হবে।",
            "বিচারকদের সিদ্ধান্ত চূড়ান্ত বলে গণ্য হবে।",
            "কোনো প্রকার অসদুপায় (মোবাইল ব্যবহার, গুগল সার্চ ইত্যাদি) ব্যবহার সম্পূর্ণভাবে নিষিদ্ধ।"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "পোস্টার ডিজাইনিং প্রতিযোগিতা",
        "info": "সৃজনশীলতা ও আবেগ একসাথে কাজ করে।",
        "img": "https://i.postimg.cc/wBw9cvqF/Whats-App-Image-2026-02-20-at-3-49-17-PM.jpg",
        "type": "Submission",
        "categories": [],
        "is_free_for_all": True,
        "rules": [
            "প্রত্যেক অংশগ্রহণকারী শুধুমাত্র একটি পোস্টার জমা দিতে পারবে; একাধিক জমা দেওয়া যাবে না।",
            "পোস্টারে কোনো অশালীন, আপত্তিকর বা অসম্মানজনক কনটেন্ট থাকা যাবে না।",
            "যদি লেখা থাকে, তবে তা অবশ্যই ভাষাগতভাবে শুদ্ধ হতে হবে (থিম অনুযায়ী বাংলা বা ইংরেজি)।",
            "ব্যক্তিগত পরিচয় (নাম, রোল নম্বর, ফোন নম্বর) উল্লেখ করা যাবে না।",
            "নম্বর বা অবস্থান নিয়ে কোনো ধরনের যোগাযোগ গ্রহণযোগ্য হবে না।",
            "কোনো ধরনের কপি, প্লেজারিজম বা অন্যের পোস্টার ব্যবহার করলে তাৎক্ষণিকভাবে বাতিল/অযোগ্য ঘোষণা করা হবে।",
            "বিচারকদের সিদ্ধান্তই চূড়ান্ত।"
        ],
        "submission_guideline": [
            "ডিজাইন অবশ্যই A5 সাইজ (১৪.৮ x ২১.০ সেমি / ১৪৮ x ২১০ মিমি) অনুপাতে হতে হবে।",
            "একটি গুগল ড্রাইভ ফোল্ডারে কাজ আপলোড করতে হবে। সেখানে চূড়ান্ত ডিজাইন (PNG/JPG) এবং র’ এডিটেবল ফাইল (PSD/AI ইত্যাদি) দিতে হবে।",
            "যদি Canva-তে ডিজাইন করা হয়, তবে সবার জন্য অ্যাক্সেস দেওয়া একটি এডিটেবল Canva লিংক শেয়ার করতে হবে।"
        ],
        "price": 100,
        "current_participants": 0
    },
    {
        "name": "চিঠি লেখার প্রতিযোগিতা",
        "img": "https://scontent.fdac138-1.fna.fbcdn.net/v/t39.30808-6/489321654_1081130850714425_1952282943695779918_n.jpg?_nc_cat=110&ccb=1-7&_nc_sid=13d280&_nc_ohc=46vJ-tm2Bx0Q7kNvwH72EpM&_nc_oc=AdmSjOCQnithG6VvTNodLyE3t7MfMiOJ8azIzTD0kctzr1k5088zBBzESX6ci2yO5E4&_nc_zt=23&_nc_ht=scontent.fdac138-1.fna&_nc_gid=S5egzBqnK-QgFZLS_PT9qg&oh=00_Aft0gdL2_I9BIzgfUJw5yhEPzvA9bNcDMUNlrtF9d5ySrg&oe=699CB0E2",
        "type": "Solo",
        "categories": [
            "J",
            "S",
            "HS"
        ],
        "is_free_for_all": False,
        "rules": [
            "অংশগ্রহণকারীদের নির্ধারিত বিষয়ের ওপর একটি চিঠি লিখতে হবে।",
            "অংশগ্রহণকারীদের নির্ধারিত বিষয়ের ওপর একটি চিঠি লিখতে হবে।",
            "চিঠিটি ব্যক্তিগত (অনানুষ্ঠানিক) ধাঁচের হতে হবে; অতিরিক্ত আনুষ্ঠানিক ভাষা গ্রহণযোগ্য নয়।",
            "লেখার বিষয়বস্তু সম্পূর্ণভাবে অংশগ্রহণকারীর নিজস্ব চিন্তা ও অনুভূতির ওপর ভিত্তি করে হতে হবে।",
            "নকল করা বা অন্যের সহায়তা নেওয়া সম্পূর্ণ নিষিদ্ধ।",
            "কোনো অশালীন, অসম্মানজনক বা আপত্তিকর শব্দ ব্যবহার করা যাবে না।",
            "সময় : ৩০ মিনিট",
            "নির্ধারিত সময়ের মধ্যেই চিঠি সম্পন্ন করতে হবে। (সময় অতিক্রম করলে সাবমিশন বাতিল হতে পারে)",
            "মোবাইল ফোন, ইন্টারনেট বা যেকোনো ইলেকট্রনিক ডিভাইস ব্যবহার সম্পূর্ণ নিষিদ্ধ।",
            "বিচারকদের সিদ্ধান্তই চূড়ান্ত।"
        ],
        "price": 100,
        "current_participants": 0
    }
]


# unique_keys = set(itertools.chain.from_iterable(d.keys() for d in segments))

# print(unique_keys)
# data = []
# for s in segments:
#     s['current_participants'] = 0
#     data.append(s)

    
# with open('segments.json', 'w', encoding='utf-8') as f:
#     json.dump(data, f, ensure_ascii=False, indent=4)

def genrerate_segs(uri):
    extensions.client = MongoClient(uri)
    extensions.db = extensions.client.festival_db

    db = extensions.client.festival_db


    segments_collection = db.segments
    segments_collection.insert_many(segments)