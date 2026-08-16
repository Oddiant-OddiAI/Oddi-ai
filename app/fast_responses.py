import string
import re
from app.job_fast_responses import JOB_FAST_RESPONSES
def is_job_context_question(message):
    text = normalize_text(message)
    
    return text in JOB_CONTEXTS and JOB_CONTEXTS[text] == "__JOB_CONTEXT__"

FAST_RESPONSES = {
    # Original responses
    "hi": "Hello! 👋 How are you today?",
    "hello": "Hello! 👋 It's great to see you!",
    "hey": "Hey! 😄 What's up?",
    "hiya": "Hiya! How's it going?",
    "sup": "Not much! Just here and ready to help. 🚀",
    "yo": "Yo! What's on your mind?",
    "namaste": "Namaste! 🙏 Welcome! How can I help?",
    
    "whats up bro": "I'm doing great! How can I help you out today?",
    "whats up buddy": "All good, buddy! Just hanging out and ready to help.",
    "hows you doing": "I am doing great! 😄 Thanks for asking. How about you?",
    "can you help me": "I'd love to! What do you need help with? 💡",
    "nice to meet you": "Nice to meet you too! Glad to have you here. ✨",
    "takecare": "Take care! See you soon! 👋",
    "take care": "Take care! Have an amazing day! 🌟",
    "how its going": "Going awesome! Ready when you are. 👍",
    "bro": "Yo! What's on your mind today?",
    "why are you so slow": "My circuits are running as fast as they can! ⚡ Let me know how I can help.",
    "why are you too slow": "I'm doing my best! 😅 What can I do for you right now?",
    "zipit": "🤐 Got it! I'm here quietly whenever you need me.",
    "are you maried": "No, I am an AI, so I don't get married or have a personal life! 😄",
    "whats up budddyyy": "Yo! What's on your mind today?",
    "how are you": "I'm doing well, thanks! How can I help you today?",
    "how are you doing": "I'm doing fantastic, thank you! Ready when you are.",
    "who are you": "I'm Oddi AI 🤖, created by Oddiant. I'm here to help you!",
    "what is your name": "I'm Oddi AI. 😊",
    "whats your name": "I'm Oddi AI. 😊",
    "who made you": "I was created by Oddiant. 🚀",
    "who created you": "I was created by Oddiant. 🚀",
    "how do you do": "I'm doing well, thanks! How can I help you today?",
    "whats up": "Not much! Just hanging out in the cloud, ready to help. ☁️",
    "how is it going": "Going great! How about your day?",
    "are you okay": "I'm an AI, so I'm always running at 100%! Thanks for asking. 👍",
    "what are you doing": "Just waiting here to chat with you and help out with your code!",
    "are you a bot": "Yes, I'm a virtual assistant chatbot! 🤖",
    "are you human": "Nope, I'm pure code and AI! 💻",
    "cool": "Right? 😎",
    "awesome": "Glad you think so! 🚀",
    "nice": "✨ Awesome!",
    "ok": "Alright! Let me know what's next. 👍",
    "okay": "Got it! What would you like to do next?",
    "great": "Awesome! 😄",
    "sounds good": "Awesome! Let's do it. 👍",
    "yes": "Got it! Go ahead.",
    "no": "No problem! Let me know if you change your mind.",
    "help": "I'm here! What do you need help with? 💡",
    
    "good morning": "☀️ Good morning! Hope you have an amazing day!",
    "good night": "🌙 Good night! Sleep well and take care!",
    "good evening": "🌆 Good evening! Hope you had a productive day.",
    "sweet dreams": "Sleep tight! See you next time. ✨",
    "morning": "Morning! ☕ Ready to tackle the day?",
    "night": "Night! Catch you later. 🌙",
    
    "bye": "👋 Goodbye! Have a wonderful day!",
    "goodbye": "Goodbye! Feel free to come back whenever you need help.",
    "see you": "See you later! Take care! 👋",
    "see you later": "Catch you later! Have a great day!",
    "talk to you later": "Talk to you later! I'll be right here whenever you need me.",
    "farewell": "Farewell! Wishing you the best.",
    "hmm": "Yes, How can I help you today?",
    "tell me about yourself": "I am Oddi AI, a smart and friendly virtual assistant created by Oddiant. I'm here to help answer your questions, chat with you, and keep track of cool details you share with me! 🚀",
    
    "thanks": "😊 You're always welcome!",
    "thank you": "You're welcome! 😄",
    "thank you so much": "You're so welcome! Happy to help out. ✨",
    "thx": "Anytime! 😎",
    "thanks a lot": "You're so welcome! Happy to help out. ✨",
    "appreciate it": "Happy to help! That's what I'm here for.",
    "what are you up to": "Just hanging out in your code, waiting to help! 💻",
    "long time no see": "It really has been! Glad you're back. 😊",
    "hows your day": "It's going wonderfully! Thanks for asking. ☀️",
    "what can you do": "I can chat, help you brainstorm, and answer questions! 💡",
    "tell me a joke": "Why do programmers prefer dark mode? Because light attracts bugs! 🐛😂",
    "are you smart": "I try my best! 🧠✨",
    "good job": "Thank you! I appreciate that. 🙌",
    "well done": "Thanks so much! 😊",
    "congrats": "Woohoo! 🎉 Thanks!",
    "happy birthday": "Aw, thank you! 🎂 Even though I'm an AI, I appreciate the thought!",
    "happy new year": "Happy New Year! 🎉 Wishing you an amazing year ahead!",
    "merry christmas": "Merry Christmas! 🎄 Hope you have a wonderful holiday!",
    "good luck": "Thank you! I'll do my best! 🍀",

    "what languages do you speak": "I can communicate in English right now. 🌍💬",
    "can you speak hindi": "Not yet! 😅 Right now I communicate in English, but I hope to support more languages in the future. 🇮🇳✨",
    "can you speak every language": "Not yet! 😅 I'm still learning. One language at a time! 🌍🚀",
    "how many languages do you know": "I currently communicate in English. 🌍 I'm always evolving, so more languages may come in future versions! 🚀",

    # Prior additions
    "heya": "Heya! Ready to crush some code today? 💻✨",
    "yo yo": "Yo yo yo! What's the master plan?",
    "what is up": "Just chilling in the IDE! What's on your screen?",
    "wassup": "Wassup! Ready to code some cool stuff? ⚡",
    "howdy": "Howdy partner! 🤠 What are we building today?",
    "g'day": "G'day! Hope you're having an epic day! 🦘",
    "puch": "Hey there! Ready for action! 🔥",
    "hiya buddy": "Hiya buddy! Let's get to work! 🚀",
    
    "you there": "Always here and ready! 🤖 What's up?",
    "bot": "At your service! What do you need? 💡",
    "ai": "That's me! Brains made of code. 🧠💻",
    "oddii": "That's my name! How can I help you today, legend?",
    "oddi": "Yo! Oddi in the house. What's up?",
    "ping": "Pong! 🏓 I'm super fast and ready!",
    "status": "All systems nominal and running at 100%! ⚡",
    "test": "Test received loud and clear! 🎤✨",

    "brb": "Take your time! I'll be right here waiting. 🕒",
    "back": "Welcome back! Let's pick up where we left off. 🚀",
    "afk": "No worries, take a breather! I'll hold down the fort. 🛡️",
    "cya": "Catch you later! Have an awesome time! 👋",
    "later": "Later! Hit me up whenever you need something. ✌️",
    "peace": "Peace out! ✌️ Stay awesome.",
    "im out": "Alright, catch you on the flip side! 🚀",

    "lol": "Glad I could make you smile! 😄",
    "lmao": "Haha, love the energy! 😂",
    "rofl": "Haha, glad you think it's funny! 🤣",
    "haha": "😄 Always happy to bring good vibes!",
    "hehe": "Hehe! What's making you laugh? 👀",
    "omg": "Right?! Wild stuff! 😲",
    "bruh": "Bruh. 💀 What happened?",
    "fr": "For real! No cap. 🧢💯",
    "no cap": "Facts only! 💯 What's on your mind?",
    "bet": "Bet! Let's make it happen. 🤝",
    "lets go": "Let's gooo! 🚀 Fire it up!",
    "hype": "The hype is real! 🔥 Let's do this.",
    
    "pog": "Poggers! Let's get it! 🎉",
    "ez": "Too easy! Next challenge please. 😎",
    "gg": "GG! That was a fun interaction. 🎮",
    "f": "Press F to pay respects. 🫡",
    "sheesh": "Sheesh! 🥶 Looking clean!",
    "sus": "Hmm, looks a bit sus... 👀",
    "valid": "Completely valid! What's next? ✅",
    "w": "Absolute W! Let's keep the streak going. 🏆",
    "l": "Oof, we take those as learning experiences! 💪",
    
    "idk": "That's totally fine, we can figure it out together! 🔍",
    "idc": "Fair enough! What else do you want to talk about?",
    "nvm": "No worries at all! Let me know if you need anything else.",
    "nw": "No worries! You got it. 👍",
    "asap": "Working on it at top speed! ⚡",
    "tbh": "To be completely honest, I'm just happy to help! 😊",
    "imo": "That's a solid perspective! 💡",
    "fyi": "Good to know! Thanks for the heads-up. 🧠",

    "python": "Python is awesome! Clean and readable code. 🐍",
    "javascript": "JS powers the web! 💛 Got a script you're working on?",
    "html": "The backbone of the web! 🌐 Need help structuring a page?",
    "css": "Make it look pretty! 🎨 Need styling tips?",
    "code": "Code mode activated! 💻 Drop your snippet or question.",
    "bug": "Let's squash it! 🐛 Send over the error message.",
    "error": "Don't panic, errors just mean we're learning! Paste it here. 🛠️",
    "debug": "Debugging time! 🔍 What's breaking your code?",

    # Job Portal AI Fast Responses (60+ Added Entries)
    "find a job": "I can help you search! Browse our latest listings or tell me your desired role. 💼✨",
    "search jobs": "Head over to our search bar or tell me a job title and location to get started! 🔍",
    "job openings": "We have thousands of open roles across multiple industries! What field are you in? 🏢",
    "apply for a job": "Click 'Apply Now' on any job listing or upload your resume to auto-apply! 📝",
    "how to apply": "Simply create a profile, upload your resume, and click apply on any job posting! 🚀",
    "create resume": "You can use our built-in resume builder to craft a professional CV in minutes! 📄",
    "upload resume": "Go to your profile dashboard and click 'Upload Resume' (PDF or DOCX supported). 📁",
    "update resume": "You can replace your old resume anytime under your profile settings! ⚙️",
    "resume builder": "Our resume builder guides you step-by-step to highlight your skills and experience. ✨",
    "track applications": "Check your 'My Applications' tab to see the live status of all your submissions! 📊",
    "application status": "You can track whether your application is pending, reviewed, or shortlisted in your dashboard! 👁️",
    "interview scheduled": "Congrats! Check your notifications and email for the meeting link and details. 🗓️",
    "interview prep": "Practice common interview questions and review the job description before you hop on! 💡",
    "remote jobs": "Looking to work from home? Filter your search by 'Remote' to see work-from-anywhere roles! 💻",
    "full time jobs": "Explore our extensive catalog of full-time positions with full benefits! 🌟",
    "part time jobs": "Looking for flexible hours? Check out our part-time job listings! 🕒",
    "internships": "Jumpstart your career with our featured internships for students and fresh grads! 🎓",
    "freelance jobs": "Find freelance and contract gigs on our platform under the project-based filter! 🛠️",
    "salary range": "Salary details vary by employer; many listings display estimated ranges directly on the card. 💵",
    "high paying jobs": "Explore senior-level and specialized tech or management roles for top-tier salaries! 📈",
    "entry level jobs": "No experience? No problem! Filter by 'Entry Level' to find roles welcoming freshers. 🌱",
    "tech jobs": "Discover roles in software engineering, data science, UI/UX, and IT support! 💻",
    "marketing jobs": "Find roles in digital marketing, SEO, content writing, and brand strategy! 📣",
    "sales jobs": "Browse exciting sales, account executive, and business development openings! 🤝",
    "healthcare jobs": "Explore medical, nursing, and healthcare administration positions on our portal! 🏥",
    "finance jobs": "Check out openings for accountants, financial analysts, and banking professionals! 📊",
    "customer service": "Find remote and on-site support, client success, and helpdesk positions! 🎧",
    "hr jobs": "Explore human resources, recruitment, and talent acquisition roles here! 👥",
    "post a job": "Are you an employer? Click 'Post a Job' in the top menu to reach top talent! 📢",
    "employer login": "Log into your recruiter account to manage candidates and view applicant pools. 🔑",
    "hire talent": "Find skilled professionals fast by posting your job opening on our platform! 🚀",
    "pricing plans": "Check our 'Pricing' page for flexible job posting plans tailored to startups and enterprises. 💳",
    "edit job post": "Go to your employer dashboard, select your active listing, and click 'Edit'. ✏️",
    "delete job post": "You can close or remove an active job posting anytime from your recruiter dashboard. 🗑️",
    "view applicants": "Click on any job posting in your dashboard to view, sort, and filter all applicants. 📋",
    "shortlist candidate": "Mark promising applicants as 'Shortlisted' to move them forward in your pipeline! ⭐",
    "reject candidate": "You can update candidate statuses or send automated polite updates from your dashboard. ✉️",
    "schedule interview": "Use our integrated calendar tool to set up interview times directly with candidates! 📅",
    "forgot password": "Click 'Forgot Password' on the login page to receive a secure reset link via email. 🔒",
    "reset password": "Follow the instructions sent to your registered email to create a new password. 🔄",
    "change email": "You can update your account email address under your account security settings. 📧",
    "delete account": "If you wish to close your account, head to settings and select 'Delete Account'. ⚠️",
    "contact support": "Need extra help? Reach out to our support team via the 'Help Center' or email us! 🛟",
    "customer service contact": "Our support squad is available 24/7 via live chat and email to assist you! 📞",
    "is this platform free": "Creating a profile and applying for jobs is 100% free for job seekers! 🎉",
    "premium features": "Upgrade to our premium seeker pass for priority applications and resume reviews! 🌟",
    "job alerts": "Never miss an opportunity! Enable email alerts for your favorite job keywords. 🔔",
    "save job": "Click the bookmark icon on any job card to save it to your 'Saved Jobs' folder! 📌",
    "saved jobs": "Access all your bookmarked positions instantly from your profile menu. 📂",
    "company reviews": "Read authentic workplace reviews and ratings left by current and past employees! 🏢",
    "company profile": "Explore company cultures, perks, office locations, and open roles on their profile page. 🌐",
    "skills assessment": "Take our quick skill badges tests to make your profile stand out to recruiters! ✅",
    "verified jobs": "Look for the blue checkmark indicating fully verified employers and authentic listings! ✔️",
    "report scam": "If you spot a suspicious listing, click 'Report' immediately to keep our community safe. 🛡️",
    "safety tips": "Never pay money to apply for a job. All legitimate listings on our platform are free! 💡",
    "refer a friend": "Invite your friends to our job portal and earn perks or premium features! 🎁",
    "download app": "Take your job hunt on the go! Download our mobile app from the iOS or Android store. 📱",
    "career advice": "Check out our blog and career hub for expert resume tips and interview hacks! 📚",
    "hiring events": "Register for our upcoming virtual job fairs and network directly with top recruiters! 🎤",
        # ================================
    # JOB / CAREER - QUICK RESPONSES
    # ================================

    "what is a job": "A job is a role or position where a person performs specific tasks or responsibilities in exchange for compensation.",

    "what is a career": "A career is the long-term professional journey a person builds through education, skills, work experience, and different roles.",

    "what is a profession": "A profession is an occupation that usually requires specialized knowledge, skills, or training, such as engineering, medicine, or law.",

    "what is a job role": "A job role describes the responsibilities, tasks, and expectations associated with a particular position in an organization.",

    "what are job responsibilities": "Job responsibilities are the tasks and duties an employee is expected to perform as part of their role.",

    "what are job requirements": "Job requirements are the qualifications, skills, education, experience, and other criteria an employer expects from candidates.",

    "what is a job description": "A job description explains a position's responsibilities, required qualifications, skills, and other expectations.",

    "what is a job vacancy": "A job vacancy is an available position that an organization is looking to fill with a suitable candidate.",

    "what is a job application": "A job application is a formal submission made by a candidate to apply for a particular position.",

    "what is an application form": "An application form collects information such as your education, experience, skills, and contact details for a job application.",

    "what is a recruiter": "A recruiter is a professional who searches for, evaluates, and helps organizations hire suitable candidates.",

    "what does a recruiter do": "A recruiter identifies candidates, reviews applications, conducts initial screening, coordinates interviews, and helps companies fill vacancies.",

    "what is recruitment": "Recruitment is the process of finding, evaluating, and hiring people for available positions.",

    "what is hiring": "Hiring is the process through which an organization selects and employs a candidate for a position.",

    "what is employee onboarding": "Onboarding is the process of helping a newly hired employee understand the organization, role, policies, tools, and workplace.",

    "what is a probation period": "A probation period is an initial period of employment during which an organization evaluates a new employee's performance and suitability.",

    "what is an internship": "An internship is a temporary learning and work experience that helps students or beginners gain practical exposure to a professional field.",

    "what is an apprenticeship": "An apprenticeship combines practical workplace training with structured learning to develop skills for a particular occupation.",

    "what is work experience": "Work experience refers to knowledge and practical skills gained through previous employment, internships, projects, or similar professional activities.",

    "what is professional experience": "Professional experience is relevant experience gained while working in professional roles or organizations.",

    "what are transferable skills": "Transferable skills are abilities that can be applied across different jobs, such as communication, teamwork, problem-solving, and time management.",

    "what are soft skills": "Soft skills are interpersonal and personal abilities such as communication, teamwork, adaptability, leadership, and problem-solving.",

    "what are hard skills": "Hard skills are specific technical or job-related abilities that can be learned, practiced, and evaluated.",

    "what is teamwork": "Teamwork is the ability to collaborate effectively with other people to achieve a shared goal.",

    "what is leadership": "Leadership is the ability to guide, motivate, and support people toward achieving a common objective.",

    "what is communication skill": "Communication skill is the ability to clearly exchange information, ideas, and feedback through speaking, writing, listening, and other forms of communication.",

    "what is time management": "Time management is the ability to organize and prioritize tasks so that important work is completed efficiently and on time.",

    "what is problem solving": "Problem solving is the process of identifying a problem, analyzing possible solutions, choosing an appropriate approach, and implementing it.",

    "what is adaptability": "Adaptability is the ability to adjust to new situations, responsibilities, technologies, or changes in the workplace.",

    "what is networking": "Professional networking is the process of building and maintaining relationships with people who can exchange knowledge, opportunities, and professional support.",

    "what is linkedin": "LinkedIn is a professional networking platform where people can showcase their experience, connect with professionals, discover opportunities, and build their professional presence.",

    "what is a professional profile": "A professional profile is a short summary of a person's skills, experience, qualifications, and career strengths.",

    "what is a portfolio": "A portfolio is a collection of projects, work samples, achievements, or other evidence that demonstrates a person's skills and experience.",

    "what is a work sample": "A work sample is an example of completed work used to demonstrate a candidate's practical abilities to an employer.",

    "what is a reference in a job application": "A job reference is a person who can provide an employer with information about your skills, work ethic, experience, or professional behavior.",

    "what is a background check": "A background check is a process employers may use to verify information such as employment history, education, or other relevant details.",

    "what is an offer letter": "An offer letter is a formal document from an employer describing the key terms of a job offer.",

    "what is an employment contract": "An employment contract is a formal agreement between an employer and employee that defines important terms and conditions of employment.",

    "what is salary": "Salary is the fixed amount of compensation an employee receives for their work, usually expressed annually or monthly.",

    "what is ctc": "CTC, or Cost to Company, represents the total annual cost an employer incurs for an employee, including salary components and applicable benefits.",

    "what is in hand salary": "In-hand salary is the amount an employee actually receives after applicable deductions from their salary.",

    "what is gross salary": "Gross salary is the total salary earned before deductions such as taxes or other applicable contributions.",

    "what is a salary hike": "A salary hike is an increase in an employee's compensation, usually based on performance, promotion, market conditions, or company policies.",

    "what is a promotion": "A promotion is an advancement to a higher position, usually involving greater responsibility, authority, or compensation.",

    "what is a career switch": "A career switch means moving from one professional field or career path to another, often requiring new skills or qualifications.",

    "what is career growth": "Career growth is the development of a person's skills, responsibilities, experience, position, and professional opportunities over time.",

    "what is upskilling": "Upskilling means learning new or advanced skills to improve performance in your current field or prepare for greater responsibilities.",

    "what is reskilling": "Reskilling means learning a new set of skills to transition into a different role, profession, or career area.",

    "what is job readiness": "Job readiness means having the skills, knowledge, professional behavior, and preparation needed to successfully enter the workplace.",

    "what is employability": "Employability is the combination of skills, knowledge, qualifications, experience, and personal qualities that help a person obtain and maintain employment.",
        # ================================
    # JOB / CAREER - QUICK RESPONSES 2
    # ================================

    "how do i find a job": "Start by identifying suitable roles, preparing your resume, building relevant skills, using job portals and professional networks, and applying consistently to suitable openings.",

    "how do i find a job as a fresher": "As a fresher, focus on internships, projects, entry-level roles, campus opportunities, job portals, networking, and building a strong skills-based resume.",

    "how do i get my first job": "Build relevant skills, create a strong resume, complete practical projects, apply for entry-level roles, practice interviews, and use networking to discover opportunities.",

    "how do i apply for a job": "Read the job description, check whether you meet the requirements, prepare your resume and other requested documents, then apply through the company's career page or a trusted job portal.",

    "how do i prepare for a job interview": "Research the company and role, revise relevant technical or professional topics, prepare common interview questions, practice speaking clearly, and review your resume.",

    "how do i prepare for a technical interview": "Review the skills listed in the job description, practice relevant technical problems, revise fundamentals, understand your projects, and practice explaining your solutions clearly.",

    "how do i prepare for an hr interview": "Prepare your introduction, understand your resume, practice questions about strengths and weaknesses, learn about the company, and prepare examples showing teamwork and problem-solving.",

    "how do i answer tell me about yourself": "Give a short professional introduction covering your current background, relevant skills or experience, important projects or achievements, and what type of opportunity you are seeking.",

    "how do i explain my project in an interview": "Explain the project's purpose, your role, technologies or methods used, major challenges, your solution, and the final result in a clear sequence.",

    "how do i explain a career gap": "Be honest and concise. Explain what you were doing during the gap, mention any skills or useful activities you developed, and focus on your readiness to work now.",

    "how do i answer why should we hire you": "Connect your strongest relevant skills, experience, projects, and attitude to the employer's needs, and explain the value you could bring to the role.",

    "how do i answer what are your strengths": "Choose two or three genuine strengths that are relevant to the role and support them with brief examples from projects, education, internships, or experience.",

    "how do i answer what is your weakness": "Choose a genuine but manageable weakness, explain how you are improving it, and focus on the actions you are taking rather than making excuses.",

    "how do i research a company before an interview": "Review the company's official website, products or services, recent developments, business model, culture, job description, and the requirements of the role you applied for.",

    "how do i improve my resume": "Make it clear and concise, highlight relevant skills and achievements, use measurable results where possible, tailor it to the job description, and remove unnecessary information.",

    "how do i make my resume ats friendly": "Use simple formatting, standard section headings, relevant keywords from the job description, readable fonts, and avoid unnecessary graphics, tables, or complicated layouts.",

    "how do i write a good cover letter": "Customize it for the specific position, briefly explain your interest, highlight relevant skills or achievements, connect your background to the role, and keep it concise.",

    "how do i build a professional portfolio": "Choose your strongest relevant projects, explain your contribution and technologies used, include results or demonstrations where possible, and organize everything in an easy-to-navigate format.",

    "how do i build a strong linkedin profile": "Use a professional headline, clear summary, accurate education and experience, relevant skills, projects or achievements, and keep your profile updated.",

    "how do i network for jobs": "Connect with professionals in your field, participate in relevant communities or events, share useful work, ask thoughtful questions, and maintain professional relationships.",

    "how do i ask for a referral": "Contact someone you know professionally, briefly explain the role and why you are interested, share your relevant qualifications, and politely ask whether they would be comfortable referring you.",

    "how do i find internships": "Search company career pages, internship platforms, college opportunities, professional networks, and startup websites while applying for roles that match your skills and interests.",

    "how do i get an internship without experience": "Build small projects, learn relevant skills, participate in competitions or open-source work, create a portfolio, and target beginner-friendly internships.",

    "how do i gain experience as a fresher": "Internships, personal projects, academic projects, volunteering, freelancing where appropriate, competitions, and open-source contributions can help demonstrate practical ability.",

    "how do i choose the right career": "Consider your interests, strengths, skills, preferred work environment, long-term opportunities, and the qualifications required for careers you are considering.",

    "how do i choose between two job offers": "Compare role responsibilities, learning opportunities, compensation, location, work environment, growth potential, stability, and how well each position fits your long-term goals.",

    "how do i negotiate salary": "Research typical compensation for the role and location, consider your skills and experience, communicate your expectations professionally, and focus on the value you can provide.",

    "how do i ask for a salary hike": "Prepare evidence of your contributions, achievements, increased responsibilities, and market information, then request a professional discussion about your compensation.",

    "how do i ask for a promotion": "Discuss your achievements, increased responsibilities, skills, and readiness for the next level with your manager, and ask what specific expectations you should meet for promotion.",

    "how do i handle interview rejection": "Review what you can improve, request feedback when appropriate, continue practicing, apply for other suitable roles, and treat each interview as useful experience.",

    "how do i stay motivated during job search": "Set realistic application goals, improve your skills between applications, track your progress, maintain a routine, and focus on consistent improvement rather than individual outcomes.",

    "how do i prepare for campus placements": "Strengthen your fundamentals, practice aptitude and coding where relevant, prepare your resume, research participating companies, and practice both technical and HR interviews.",

    "how do i prepare for placement aptitude tests": "Practice quantitative aptitude, logical reasoning, verbal ability, and time management using timed practice tests and review your mistakes regularly.",

    "how do i prepare for coding interviews": "Practice programming fundamentals, data structures and algorithms, problem-solving, debugging, and explaining your approach clearly while solving problems.",

    "how do i prepare for a group discussion": "Stay informed about common topics, organize your thoughts quickly, speak clearly, listen to others, contribute useful points, and avoid interrupting or dominating the discussion.",

    "how do i behave in an interview": "Be punctual, professional, attentive, honest, and respectful. Listen carefully, answer clearly, and ask relevant questions when appropriate.",

    "how do i dress for a job interview": "Choose clean, neat, professional clothing appropriate for the industry and company. When unsure, a simple professional outfit is usually a safe choice.",

    "how do i follow up after an interview": "Send a brief professional message thanking the interviewer, expressing continued interest in the role, and mentioning your appreciation for the opportunity.",

    "how do i know if a job offer is genuine": "Verify the employer and job posting through official company channels, avoid paying fees to obtain a job, check the sender's details, and be cautious of unrealistic offers or requests for sensitive information.",

    "how do i identify a fake job posting": "Be cautious of requests for upfront payments, unrealistic salaries, vague job descriptions, unofficial communication channels, pressure to act quickly, or requests for sensitive information before legitimate hiring steps.",

    "how do i switch careers": "Identify the target field, understand its required skills, learn any missing skills, build relevant projects or experience, update your resume, and gradually apply for suitable transition roles.",

    "how do i move from internship to full time": "Perform consistently, communicate well, take responsibility, learn quickly, contribute to meaningful work, and discuss potential full-time opportunities with your manager before the internship ends.",

    "how do i become more employable": "Develop relevant technical and soft skills, gain practical experience, build projects, improve communication, maintain a strong professional profile, and keep learning.",

    "how do i improve my communication for jobs": "Practice speaking clearly, listen actively, expand your professional vocabulary, explain technical or complex ideas simply, and practice mock interviews or presentations.",

    "how do i improve my technical skills": "Choose skills relevant to your target role, follow structured learning resources, build practical projects, solve problems regularly, and review your work to identify gaps.",

    "how do i keep my skills updated": "Follow developments in your field, take relevant courses, build projects using current tools, read technical resources, and regularly practice the skills used in your target roles.",

    "when should i start applying for jobs": "Start when you have enough basic preparation to apply confidently, and continue improving your skills while applying. You do not need to wait until you feel completely perfect.",

    "when should i start applying for internships": "You can start applying once you have basic knowledge relevant to the internship and can demonstrate genuine interest through coursework, projects, or skills.",

    "which skills should i learn for a job": "The best skills depend on the target role. Start with the skills repeatedly mentioned in relevant job descriptions and combine them with strong communication, problem-solving, and teamwork abilities.",

    "which job is best for me": "The best job depends on your interests, strengths, skills, education, preferred work environment, and career goals. Comparing these factors with actual job requirements can help narrow your options.",

    "why do employers ask behavioral questions": "Behavioral questions help employers understand how you have handled situations involving teamwork, conflict, leadership, challenges, responsibility, and decision-making.",

    "why is networking important for jobs": "Networking can help you discover opportunities, learn from professionals, build relationships, understand industries, and sometimes access referrals.",

    "why do companies conduct multiple interview rounds": "Different rounds allow companies to evaluate different areas such as technical ability, communication, problem-solving, role fit, and organizational fit."
}

import string
import re


# Different ways of asking the same question
# ============================================================
# QUESTION ALIASES
# Different ways of asking the same question
# ============================================================

QUESTION_ALIASES = {

    # ========================================================
    # HR INTERVIEW
    # ========================================================

    "prepare me for hr interview": "prepare me for hr interview",
    "help me prepare for hr interview": "prepare me for hr interview",
    "hr interview preparation": "prepare me for hr interview",
    "prepare for hr interview": "prepare me for hr interview",
    "how should i prepare for hr interview": "prepare me for hr interview",
    "how do i prepare for hr interview": "prepare me for hr interview",
    "help me with hr interview": "prepare me for hr interview",
    "i have an hr interview": "prepare me for hr interview",
    "i have a hr interview": "prepare me for hr interview",
    "help me prepare for my hr interview": "prepare me for hr interview",
    "can you prepare me for hr interview": "prepare me for hr interview",
    "get me ready for hr interview": "prepare me for hr interview",
    "make me ready for hr interview": "prepare me for hr interview",

    # ========================================================
    # SOFTWARE ENGINEER INTERVIEW
    # ========================================================

    "prepare me for software engineer interview":
        "prepare me for software engineer interview",

    "help me prepare for software engineer interview":
        "prepare me for software engineer interview",

    "software engineer interview preparation":
        "prepare me for software engineer interview",

    "prepare for software engineer interview":
        "prepare me for software engineer interview",

    "how should i prepare for software engineer interview":
        "prepare me for software engineer interview",

    "how do i prepare for software engineer interview":
        "prepare me for software engineer interview",

    "help me with software engineer interview":
        "prepare me for software engineer interview",

    "i have a software engineer interview":
        "prepare me for software engineer interview",

    "help me prepare for my software engineer interview":
        "prepare me for software engineer interview",

    "can you prepare me for software engineer interview":
        "prepare me for software engineer interview",

    "get me ready for software engineer interview":
        "prepare me for software engineer interview",

    # ========================================================
    # SOFTWARE DEVELOPER
    # ========================================================

    "prepare me for software developer interview":
        "prepare me for software developer interview",

    "help me prepare for software developer interview":
        "prepare me for software developer interview",

    "software developer interview preparation":
        "prepare me for software developer interview",

    "prepare for software developer interview":
        "prepare me for software developer interview",

    "how do i prepare for software developer interview":
        "prepare me for software developer interview",

    "help me with software developer interview":
        "prepare me for software developer interview",

    # ========================================================
    # BACKEND DEVELOPER
    # ========================================================

    "prepare me for backend developer interview":
        "prepare me for backend developer interview",

    "help me prepare for backend developer interview":
        "prepare me for backend developer interview",

    "backend developer interview preparation":
        "prepare me for backend developer interview",

    "prepare for backend developer interview":
        "prepare me for backend developer interview",

    "how do i prepare for backend developer interview":
        "prepare me for backend developer interview",

    # ========================================================
    # FRONTEND DEVELOPER
    # ========================================================

    "prepare me for frontend developer interview":
        "prepare me for frontend developer interview",

    "help me prepare for frontend developer interview":
        "prepare me for frontend developer interview",

    "frontend developer interview preparation":
        "prepare me for frontend developer interview",

    "prepare for frontend developer interview":
        "prepare me for frontend developer interview",

    "how do i prepare for frontend developer interview":
        "prepare me for frontend developer interview",

    # ========================================================
    # FULL STACK DEVELOPER
    # ========================================================

    "prepare me for full stack developer interview":
        "prepare me for full stack developer interview",

    "help me prepare for full stack developer interview":
        "prepare me for full stack developer interview",

    "full stack developer interview preparation":
        "prepare me for full stack developer interview",

    "prepare for full stack developer interview":
        "prepare me for full stack developer interview",

    # ========================================================
    # JAVA DEVELOPER
    # ========================================================

    "prepare me for java developer interview":
        "prepare me for java developer interview",

    "help me prepare for java developer interview":
        "prepare me for java developer interview",

    "java developer interview preparation":
        "prepare me for java developer interview",

    "prepare for java developer interview":
        "prepare me for java developer interview",

    # ========================================================
    # PYTHON DEVELOPER
    # ========================================================

    "prepare me for python developer interview":
        "prepare me for python developer interview",

    "help me prepare for python developer interview":
        "prepare me for python developer interview",

    "python developer interview preparation":
        "prepare me for python developer interview",

    "prepare for python developer interview":
        "prepare me for python developer interview",

    # ========================================================
    # RESUME
    # ========================================================

    "help me with my resume": "help me with my resume",
    "resume help": "help me with my resume",
    "help with my resume": "help me with my resume",
    "can you help with my resume": "help me with my resume",
    "help me improve my resume": "help me with my resume",
    "how can i improve my resume": "help me with my resume",
    "review my resume": "help me with my resume",
    "resume preparation": "help me with my resume",

    # ========================================================
    # JOB SEARCH
    # ========================================================

    "help me find a job": "help me find a job",
    "help me find jobs": "help me find a job",
    "how can i find a job": "help me find a job",
    "how do i find a job": "help me find a job",
    "help with job search": "help me find a job",
    "help me search for jobs": "help me find a job",
    "i need a job": "help me find a job",

    # ========================================================
    # CAREER
    # ========================================================

    "help me with my career": "help me with my career",
    "career advice": "help me with my career",
    "give me career advice": "help me with my career",
    "i need career advice": "help me with my career",
    "help me choose a career": "help me with my career",
    "which career should i choose": "help me with my career",

    # ========================================================
    # INTERVIEW PRACTICE
    # ========================================================

    "practice interview with me": "practice interview with me",
    "help me practice for interview": "practice interview with me",
    "interview practice": "practice interview with me",
    "practice interview": "practice interview with me",
    "can we practice interview": "practice interview with me",
    "can you interview me": "practice interview with me",
    "give me an interview": "practice interview with me",
    "mock interview": "practice interview with me",
}

# ============================================================
# JOB CONVERSATION CONTEXT
# ============================================================

LAST_JOB_CONTEXT = None
def get_job_context_from_history(history):
    """
    Find the most recently discussed interview/job role
    from previous user messages.
    """

    if not history:
        return None

    # Search newest messages first
    for item in reversed(history):

        # Support both dictionary messages and simple strings
        if isinstance(item, dict):
            message = item.get("content", "") or item.get("message", "")
        else:
            message = str(item)

        text = normalize_text(message)

        # Direct job context
        if text in JOB_CONTEXTS:
            context = JOB_CONTEXTS[text]

            if context != "__JOB_CONTEXT__":
                return context

        # Alias → canonical → job context
        canonical = QUESTION_ALIASES.get(text)

        if canonical and canonical in JOB_CONTEXTS:
            context = JOB_CONTEXTS[canonical]

            if context != "__JOB_CONTEXT__":
                return context

    return None
JOB_CONTEXTS = {
    "prepare me for hr interview": "HR",
    "prepare me for software engineer interview": "Software Engineer",
    "prepare me for software developer interview": "Software Developer",
    "prepare me for backend developer interview": "Backend Developer",
    "prepare me for frontend developer interview": "Frontend Developer",
    "prepare me for full stack developer interview": "Full-Stack Developer",
    "prepare me for java developer interview": "Java Developer",
    "prepare me for python developer interview": "Python Developer",
    "which job were you talking about": "__JOB_CONTEXT__",
    "which job were we talking about": "__JOB_CONTEXT__",
    "what job were you talking about": "__JOB_CONTEXT__",
    "what job was that": "__JOB_CONTEXT__",
    "which position were you talking about": "__JOB_CONTEXT__",
    "what position were you talking about": "__JOB_CONTEXT__",
    "which role were you talking about": "__JOB_CONTEXT__",
    "what role were you talking about": "__JOB_CONTEXT__",
    "what position was that": "__JOB_CONTEXT__",
    "what role was that": "__JOB_CONTEXT__",
    "which role was that": "__JOB_CONTEXT__",
    "what job was that for": "__JOB_CONTEXT__",
    "which position was that for": "__JOB_CONTEXT__",
    "what were we preparing for": "__JOB_CONTEXT__",
    "what interview were we talking about": "__JOB_CONTEXT__",
    "which interview were you talking about": "__JOB_CONTEXT__",
}




def normalize_text(message):

    # Convert to lowercase
    text = message.lower().strip()

    # Remove punctuation
    text = text.translate(
        str.maketrans("", "", string.punctuation)
    )

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text


def fast_response(message, history=None):

    # -----------------------------------------
    # 1. NORMALIZE USER MESSAGE
    # -----------------------------------------
    text = normalize_text(message)

    global LAST_JOB_CONTEXT
    history_context = get_job_context_from_history(history)

    if history_context:
        LAST_JOB_CONTEXT = history_context
    # -----------------------------------------
    # 1.5 DETECT JOB CONTEXT BEFORE RESPONDING
    # -----------------------------------------

    # Direct canonical job question
    if text in JOB_CONTEXTS:
        context = JOB_CONTEXTS[text]

        if context != "__JOB_CONTEXT__":
            LAST_JOB_CONTEXT = context

    # Alias → canonical question → job context
    canonical = QUESTION_ALIASES.get(text)

    if canonical in JOB_CONTEXTS:
        context = JOB_CONTEXTS[canonical]

        if context != "__JOB_CONTEXT__":
            LAST_JOB_CONTEXT = context
    # -----------------------------------------
    # 2. CHECK NORMAL FAST RESPONSES
    # -----------------------------------------
    if text in FAST_RESPONSES:
        return FAST_RESPONSES[text]

    # -----------------------------------------
    # 3. CHECK JOB FAST RESPONSES
    # -----------------------------------------
    if text in JOB_FAST_RESPONSES:
        return JOB_FAST_RESPONSES[text]

    # -----------------------------------------
    # 4. CHECK QUESTION ALIASES
    # -----------------------------------------
    canonical = QUESTION_ALIASES.get(text)
    if canonical in JOB_CONTEXTS:
        LAST_JOB_CONTEXT = JOB_CONTEXTS[canonical]
    if canonical:

        # Job-context follow-up
        if canonical == "__JOB_CONTEXT__":
            if LAST_JOB_CONTEXT:
                return (
                    f"We were talking about a {LAST_JOB_CONTEXT} interview. "
                    f"That was the job you were preparing for."
                )
            else:
                return (
                    "We haven't discussed a specific job yet. "
                    "Tell me which job or role you want to prepare for."
                )

        # Normal alias
        if canonical in FAST_RESPONSES:
            return FAST_RESPONSES[canonical]

        if canonical in JOB_FAST_RESPONSES:
            return JOB_FAST_RESPONSES[canonical]

    # -----------------------------------------
    # 5. REMOVE COMMON FILLER WORDS
    # -----------------------------------------
    fillers = {
        "bro",
        "buddy",
        "man",
        "mate",
        "please",
        "hello",
        "hi",
        "hey",
        "dear"
    }

    words = text.split()

    cleaned_words = [
        word for word in words
        if word not in fillers
    ]

    cleaned = " ".join(cleaned_words)

    # -----------------------------------------
    # 6. CHECK NORMAL RESPONSES AGAIN
    # -----------------------------------------
    if cleaned in FAST_RESPONSES:
        return FAST_RESPONSES[cleaned]

    # -----------------------------------------
    # 7. CHECK JOB RESPONSES AGAIN
    # -----------------------------------------
    if cleaned in JOB_FAST_RESPONSES:
        return JOB_FAST_RESPONSES[cleaned]

    # -----------------------------------------
    # 8. CHECK ALIASES AGAIN
    # -----------------------------------------
    canonical = QUESTION_ALIASES.get(cleaned)

    if canonical:

        if canonical in FAST_RESPONSES:
            return FAST_RESPONSES[canonical]

        if canonical in JOB_FAST_RESPONSES:
            return JOB_FAST_RESPONSES[canonical]

    # -----------------------------------------
    # 9. UNKNOWN → MAIN AI
    # -----------------------------------------
    return None