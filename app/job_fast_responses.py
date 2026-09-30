import re
import string

JOB_FAST_RESPONSES = {
#HR Interview 
"help me in preparation for hr interview": """
Absolutely! Let's prepare you for an HR interview.

An HR interview mainly checks your communication, attitude, confidence,
career goals, teamwork, adaptability, and whether you are a good fit for
the organization.

Important HR questions you should prepare:

1. Tell me about yourself.
2. What are your strengths?
3. What is your weakness?
4. Why should we hire you?
5. Why do you want to join our company?
6. Why did you choose this career?
7. Where do you see yourself in 5 years?
8. Tell me about a difficult situation you handled.
9. Tell me about a time you worked in a team.
10. How do you handle failure?
11. How do you handle pressure?
12. What motivates you?
13. Why should we choose you over other candidates?
14. Are you comfortable learning new technologies?
15. Do you have any questions for us?

A good HR answer should be honest, concise, specific, and supported by
real examples from your education, projects, internships, or experience.

During practice, I can also act as the interviewer and ask you questions
one at a time, evaluate your answers, and suggest improvements.
""",

# 2. SOFTWARE ENGINEER INTERVIEW
 

"help me in preparation for software engineer interview": """
Let's prepare you for a Software Engineer interview.

A software engineering interview usually has several areas:

1. Programming fundamentals
2. Data structures and algorithms
3. Object-oriented programming
4. Database concepts
5. Operating systems
6. Computer networks
7. Software engineering concepts
8. Problem solving
9. Projects and practical experience
10. Behavioral questions

Common technical questions include:

- What is the difference between an array and a linked list?
- What is a stack and where is it used?
- What is a queue?
- What is recursion?
- What is object-oriented programming?
- Explain inheritance, encapsulation, abstraction, and polymorphism.
- What is the difference between SQL and NoSQL?
- What is a primary key?
- What is normalization?
- What is a process and a thread?
- What is an API?
- What happens when you enter a URL into a browser?
- What is Git?
- Explain one of your projects in detail.

For coding rounds, practice solving problems while explaining your
thinking clearly.

I can prepare you through:
- Technical questions
- Coding questions
- Project questions
- HR questions
- Mock interviews
- Answer evaluation
- Follow-up questions
""",


# 3. FRESHER INTERVIEW
"help me in preparation for fresher interview": """
For a fresher interview, companies usually focus less on professional
experience and more on fundamentals, learning ability, projects,
communication, and attitude.

Prepare these areas:

1. Self introduction
2. Academic background
3. Programming fundamentals
4. Data structures
5. Database basics
6. OOP concepts
7. Operating system basics
8. Projects
9. Internships or training
10. HR questions

Important questions:

- Tell me about yourself.
- Why did you choose your degree?
- Why did you choose your specialization?
- Which programming language do you know best?
- Explain your strongest project.
- What was your contribution to the project?
- What difficulties did you face?
- What did you learn from your project?
- What are your strengths?
- What are your weaknesses?
- Why should we hire you as a fresher?
- Where do you see yourself in five years?

As a fresher, don't try to pretend that you know everything.
Demonstrating strong fundamentals and willingness to learn is more
valuable than giving complicated answers you cannot explain.
""",
# 4. TECHNICAL INTERVIEW
"help me in preparation for technical interview": """
A technical interview evaluates your technical knowledge and your ability
to solve problems.

Prepare in this order:

1. Programming fundamentals
2. Object-oriented programming
3. Data structures
4. Algorithms
5. Databases
6. Operating systems
7. Computer networks
8. APIs and web concepts
9. Git and version control
10. Your projects

For programming, be comfortable with:

- Variables and data types
- Conditions
- Loops
- Functions
- Arrays
- Strings
- Pointers or references
- Recursion
- Classes and objects
- Error handling

For problem solving, don't immediately jump to code.

Use this approach:

Understand the problem
→ Explain your approach
→ Consider edge cases
→ Write the solution
→ Test it
→ Discuss time and space complexity

Interviewers often evaluate your reasoning process, not just whether your
final code works.
""",
# 5. PYTHON DEVELOPER INTERVIEW

"help me in preparation for python developer interview": """
For a Python Developer interview, prepare both Python fundamentals and
practical development concepts.

Important Python topics:

1. Variables and data types
2. Lists, tuples, sets, and dictionaries
3. Functions
4. Lambda functions
5. List comprehensions
6. Exception handling
7. Modules and packages
8. Classes and objects
9. Inheritance
10. Decorators
11. Iterators and generators
12. File handling
13. Virtual environments
14. APIs
15. Databases
16. Testing

Common interview questions:

- What is the difference between a list and tuple?
- What is a dictionary?
- What are mutable and immutable objects?
- What is a decorator?
- What is a generator?
- What is exception handling?
- What is the difference between `==` and `is`?
- What is inheritance?
- What is a virtual environment?
- How do you connect Python to a database?
- How do you build an API using Python?
- Explain one Python project you have created.

Be prepared to write small programs during the interview.
""",
# 6. WEB DEVELOPER INTERVIEW

"help me in preparation for web developer interview": """
For a Web Developer interview, prepare frontend, backend, databases,
APIs, and basic deployment concepts.

Frontend topics:

- HTML
- CSS
- JavaScript
- DOM
- Responsive design
- Forms
- Browser storage
- HTTP basics

Backend topics:

- Server-side programming
- REST APIs
- Authentication
- Sessions
- Databases
- Error handling
- Security basics

Important questions include:

- What is HTML?
- What is the difference between HTML and CSS?
- What is JavaScript?
- What is the DOM?
- What is responsive design?
- What is an API?
- What is REST?
- What is HTTP?
- What is the difference between GET and POST?
- What is authentication?
- What is a database?
- What is the difference between frontend and backend?

You should also be able to explain at least one complete project from
frontend to backend.
""",

# 7. DATA ANALYST INTERVIEW

"help me in preparation for data analyst interview": """
A Data Analyst interview usually tests analytical thinking, statistics,
SQL, spreadsheets, data visualization, and your ability to communicate
insights.

Prepare:

1. Excel or spreadsheets
2. SQL
3. Basic statistics
4. Data cleaning
5. Data visualization
6. Python basics
7. Business reasoning
8. Communication

Common questions:

- What is SQL?
- What is the difference between WHERE and HAVING?
- What is a JOIN?
- Explain INNER JOIN and LEFT JOIN.
- What is a primary key?
- What is data cleaning?
- What is an outlier?
- What is mean, median, and mode?
- What is correlation?
- How would you handle missing data?
- How would you explain a complex dataset to a non-technical person?

For practical interviews, expect SQL queries and data interpretation
questions.
""",

# 8. HR EXECUTIVE INTERVIEW

"help me in preparation for hr executive interview": """
For an HR Executive interview, prepare both HR knowledge and people
management skills.

Important areas:

- Recruitment
- Employee onboarding
- Employee relations
- Performance management
- HR policies
- Conflict resolution
- Communication
- Employee engagement
- Basic employment concepts
- HR documentation

Common questions:

- What does an HR department do?
- What is recruitment?
- What is onboarding?
- How would you handle an employee conflict?
- How would you deal with an unhappy employee?
- How would you maintain confidentiality?
- What qualities should an HR professional have?
- How would you conduct an interview?
- How would you handle multiple hiring requirements?
- Why do you want to work in HR?

Strong communication, professionalism, confidentiality, and people
skills are especially important for this role.
""",

# 9. PROJECT MANAGER INTERVIEW

"help me in preparation for project manager interview": """
A Project Manager interview focuses on planning, communication,
leadership, risk management, deadlines, and stakeholder management.

Prepare these areas:

1. Project planning
2. Task management
3. Team coordination
4. Risk management
5. Time management
6. Communication
7. Conflict resolution
8. Budget awareness
9. Project tracking
10. Leadership

Common questions:

- How do you start a new project?
- How do you prioritize tasks?
- How do you handle a missed deadline?
- How do you handle team conflict?
- How do you manage project risks?
- How do you communicate project progress?
- How do you handle a stakeholder who changes requirements?
- How do you motivate a team?
- What would you do if the project is behind schedule?
- How do you measure project success?

Use real examples when answering leadership and problem-solving
questions.
""",

# 10. MOCK INTERVIEW

"give me a mock interview": """
Absolutely. I can conduct a realistic mock interview.

Here's how we'll do it:

1. I will act as the interviewer.
2. I will ask one question at a time.
3. You answer as if you are in a real interview.
4. I will evaluate your answer.
5. I will point out what was strong.
6. I will explain what could be improved.
7. I will ask follow-up questions when appropriate.
8. At the end, I will give you an overall evaluation.

We can simulate different interview types:

- HR interview
- Software Engineer interview
- Technical interview
- Fresher interview
- Python Developer interview
- Web Developer interview
- Data Analyst interview
- HR Executive interview
- Project Manager interview

For a realistic simulation, I won't immediately give you the answer.
You should answer first, just like a real candidate.

Let's begin:

"Tell me about yourself."
""",
   
# 11. JAVA DEVELOPER
   

"help me in preparation for java developer interview": """
For a Java Developer interview, prepare Java fundamentals, OOP,
collections, exception handling, multithreading, databases, and
problem-solving.

Important topics:

- Java syntax and data types
- Classes and objects
- Inheritance
- Encapsulation
- Abstraction
- Polymorphism
- Interfaces
- Strings
- Arrays
- Collections
- Exception handling
- Multithreading
- JDBC
- SQL
- Spring/Spring Boot basics
- REST APIs
- Git

Common questions:

- Why is Java platform independent?
- What is the difference between JDK, JRE, and JVM?
- What is OOP?
- What is the difference between an interface and abstract class?
- What is method overloading and overriding?
- What is the difference between ArrayList and LinkedList?
- What is exception handling?
- What is multithreading?
- What is JDBC?
- What is Spring Boot?

Be prepared to write Java programs and explain your approach clearly.
""",

  
# 12. FULL STACK DEVELOPER
   

"help me in preparation for full stack developer interview": """
A Full Stack Developer interview tests both frontend and backend
development along with databases, APIs, deployment, and problem-solving.

Prepare:

- HTML
- CSS
- JavaScript
- Frontend frameworks
- Backend programming
- REST APIs
- Authentication
- SQL/NoSQL databases
- Git
- Deployment
- Basic cloud concepts

Common questions:

- What is the difference between frontend and backend?
- What happens when a frontend calls an API?
- What is REST?
- What is authentication?
- What is a database?
- SQL vs NoSQL?
- What is Git?
- How do you handle errors in an API?
- How would you secure a web application?
- Explain your full-stack project.

Be ready to explain how the frontend, backend, database, and API work
together in one application.
""",

# 13. FRONTEND DEVELOPER 

"help me in preparation for frontend developer interview": """
For a Frontend Developer interview, focus on HTML, CSS, JavaScript,
browser behavior, responsive design, accessibility, and frontend
frameworks.

Prepare:

- HTML
- CSS
- JavaScript
- DOM
- Events
- Responsive design
- Flexbox
- Grid
- Forms
- Browser storage
- APIs
- React or another frontend framework
- Git

Common questions:

- What is the DOM?
- What is event bubbling?
- What is the difference between let, const, and var?
- What is responsive design?
- Flexbox vs Grid?
- What is an API?
- How do you fetch data from an API?
- How do you optimize a webpage?
- What is component-based development?
- Explain your frontend project.

You may also receive practical HTML, CSS, and JavaScript tasks.
""",

   
# 14. BACKEND DEVELOPER
   

"help me in preparation for backend developer interview": """
A Backend Developer interview focuses on server-side programming,
databases, APIs, authentication, security, and system logic.

Prepare:

- Backend programming language
- REST APIs
- HTTP
- Databases
- SQL
- Authentication
- Authorization
- Sessions
- Error handling
- Caching
- Git
- Basic system design

Common questions:

- What is a REST API?
- GET vs POST?
- Authentication vs authorization?
- What is a database transaction?
- What is indexing?
- SQL vs NoSQL?
- What is an HTTP status code?
- How do sessions work?
- How would you secure an API?
- How would you design a simple backend?

Be prepared to explain the backend architecture of your projects.
""",

   
# 15. DEVOPS ENGINEER
   

"help me in preparation for devops engineer interview": """
A DevOps Engineer interview focuses on automation, deployment,
infrastructure, monitoring, containers, and collaboration between
development and operations.

Prepare:

- Linux
- Git
- CI/CD
- Docker
- Kubernetes basics
- Cloud platforms
- Networking basics
- Infrastructure
- Monitoring
- Automation
- Security basics

Common questions:

- What is DevOps?
- What is CI/CD?
- What is Docker?
- What is a container?
- What is Kubernetes?
- What is Git?
- What is a deployment pipeline?
- What is cloud computing?
- How would you troubleshoot a failed deployment?
- How would you monitor an application?

Practical knowledge is especially important, so be ready to discuss
real deployment or automation projects.
""",

   
# 16. CLOUD ENGINEER
   

"help me in preparation for cloud engineer interview": """
A Cloud Engineer interview tests cloud computing, networking,
infrastructure, security, storage, and deployment concepts.

Prepare:

- Cloud computing
- Virtual machines
- Containers
- Networking
- Storage
- Databases
- IAM
- Security
- Monitoring
- Scalability
- High availability
- AWS/Azure/GCP basics

Common questions:

- What is cloud computing?
- What is a virtual machine?
- What is a container?
- What is scalability?
- What is high availability?
- What is IAM?
- What is a cloud region?
- What is a load balancer?
- How would you secure cloud resources?
- How would you deploy an application to the cloud?

Try to gain hands-on experience with at least one major cloud platform.
""",

   
# 17. CYBERSECURITY ANALYST
   

"help me in preparation for cybersecurity analyst interview": """
A Cybersecurity Analyst interview focuses on protecting systems,
detecting threats, responding to incidents, and understanding security
fundamentals.

Prepare:

- Networking
- Operating systems
- Authentication
- Access control
- Malware concepts
- Phishing
- Firewalls
- Encryption
- Vulnerabilities
- Incident response
- Security monitoring
- Security best practices

Common questions:

- What is cybersecurity?
- What is phishing?
- What is malware?
- What is a firewall?
- What is encryption?
- Authentication vs authorization?
- What is a vulnerability?
- What is an incident?
- How would you respond to a suspected security incident?
- How can an organization reduce security risks?

Focus on defensive security concepts and practical troubleshooting.
""",

   
# 18. SOFTWARE TESTER / QA ENGINEER
   

"help me in preparation for software tester interview": """
A Software Tester or QA Engineer interview focuses on finding defects,
testing software behavior, test planning, and quality assurance.

Prepare:

- Manual testing
- Test cases
- Test scenarios
- Bug reporting
- Regression testing
- Functional testing
- Integration testing
- System testing
- Automation testing
- API testing
- SQL basics
- Agile/Scrum

Common questions:

- What is software testing?
- What is a test case?
- What is a test scenario?
- What is a bug?
- What is regression testing?
- Verification vs validation?
- What is automation testing?
- How would you test a login page?
- How do you report a bug?
- What makes a good test case?

Interviewers may give you an application and ask you to identify possible
test cases and edge cases.
""",

   
# 19. MOBILE APP DEVELOPER
   

"help me in preparation for mobile app developer interview": """
A Mobile App Developer interview focuses on application development,
UI, APIs, databases, debugging, and mobile-specific concepts.

Prepare:

- Android/iOS fundamentals
- Programming language used for the platform
- UI development
- APIs
- Databases
- Authentication
- App lifecycle
- State management
- Notifications
- Testing
- Debugging
- App deployment

Common questions:

- Explain the lifecycle of a mobile application.
- How does a mobile app communicate with a server?
- What is an API?
- How do you store data locally?
- How do you handle authentication?
- How do you improve app performance?
- How do you debug an application?
- How do you handle network failures?
- How do you test a mobile application?
- Explain one mobile project you created.

Be ready to demonstrate or explain one complete application.
""",

   
# 20. AI / ML ENGINEER
   

"help me in preparation for ai ml engineer interview": """
An AI/ML Engineer interview combines programming, mathematics,
statistics, machine learning, data processing, and model evaluation.

Prepare:

- Python
- Data structures
- NumPy/Pandas
- Statistics
- Probability
- Linear algebra basics
- Machine learning
- Supervised learning
- Unsupervised learning
- Model evaluation
- Neural networks
- Deep learning basics
- APIs and deployment

Common questions:

- What is machine learning?
- Supervised vs unsupervised learning?
- What is overfitting?
- What is underfitting?
- What is training data?
- What is a feature?
- What is classification?
- What is regression?
- What is accuracy?
- What is precision and recall?
- What is a neural network?
- How would you deploy an ML model?

Be prepared to explain an ML project from data collection through
training, evaluation, and deployment.
""",

   
# 21. BUSINESS ANALYST
   

"help me in preparation for business analyst interview": """
A Business Analyst interview focuses on understanding business
requirements, analyzing problems, communicating with stakeholders, and
helping teams build effective solutions.

Prepare:

- Requirement gathering
- Business requirements
- Stakeholder management
- Data analysis
- Process analysis
- Documentation
- Excel
- SQL basics
- Presentations
- Problem solving
- Agile basics

Common questions:

- What does a Business Analyst do?
- How do you gather requirements?
- How do you handle conflicting requirements?
- How do you communicate with stakeholders?
- What is a business requirement?
- What is process analysis?
- How do you prioritize requirements?
- How do you handle changing requirements?
- How do you measure whether a solution is successful?
- Explain a business problem you solved.

Strong communication and analytical thinking are essential.
""",

   
# 22. DIGITAL MARKETING EXECUTIVE
   

"help me in preparation for digital marketing interview": """
A Digital Marketing interview focuses on online marketing channels,
content, search engines, advertising, analytics, and customer behavior.

Prepare:

- SEO
- SEM
- Social media marketing
- Content marketing
- Email marketing
- Online advertising
- Analytics
- Keyword research
- Conversion rates
- Campaign planning
- Branding

Common questions:

- What is digital marketing?
- What is SEO?
- What is SEM?
- What is a keyword?
- What is conversion rate?
- What is social media marketing?
- How would you promote a new product online?
- How do you measure campaign success?
- What is organic traffic?
- What is paid traffic?

Be ready to discuss how you would create and measure a marketing
campaign.
""",

   
# 23. SALES EXECUTIVE
   

"help me in preparation for sales executive interview": """
A Sales Executive interview evaluates communication, persuasion,
customer handling, target management, and problem-solving.

Prepare:

- Communication
- Lead generation
- Customer relationship management
- Product knowledge
- Negotiation
- Follow-up
- Sales targets
- Objection handling
- Customer needs
- Closing techniques

Common questions:

- Why do you want to work in sales?
- How would you convince a customer to buy a product?
- How do you handle rejection?
- How do you handle an angry customer?
- How do you achieve sales targets?
- What is lead generation?
- What is negotiation?
- How do you build customer relationships?
- How would you sell this product?
- What motivates you in sales?

For practical preparation, we can perform customer-sales roleplay.
""",

   
# 24. CUSTOMER SUPPORT EXECUTIVE
   

"help me in preparation for customer support executive interview": """
A Customer Support Executive interview focuses on communication,
patience, problem-solving, empathy, and handling customers professionally.

Prepare:

- Communication
- Active listening
- Customer service
- Problem solving
- Complaint handling
- Product knowledge
- Email/chat support
- Escalation
- Documentation
- Professional communication

Common questions:

- Why do you want to work in customer support?
- How would you handle an angry customer?
- What would you do if you don't know the answer?
- How do you prioritize multiple customers?
- How do you handle pressure?
- What is good customer service?
- When should an issue be escalated?
- How would you respond to a customer complaint?
- How do you maintain professionalism?

Interviewers may use roleplay scenarios, so practice responding calmly
and clearly.
""",

   
# 25. ACCOUNTANT
   

"help me in preparation for accountant interview": """
An Accountant interview tests accounting fundamentals, financial
records, accuracy, spreadsheets, taxation basics, and financial
reporting.

Prepare:

- Accounting principles
- Journal entries
- Ledger
- Trial balance
- Balance sheet
- Profit and loss statement
- Cash flow
- Accounts payable
- Accounts receivable
- Excel
- Accounting software
- Basic taxation concepts

Common questions:

- What is accounting?
- What is a journal entry?
- What is a ledger?
- What is a trial balance?
- What is a balance sheet?
- What is the difference between assets and liabilities?
- What is depreciation?
- What are accounts payable and receivable?
- How do you ensure financial accuracy?
- How would you handle an accounting error?

Accuracy and attention to detail are extremely important.
""",

   
# 26. FINANCIAL ANALYST
   

"help me in preparation for financial analyst interview": """
A Financial Analyst interview focuses on financial analysis, Excel,
financial statements, forecasting, valuation, and business reasoning.

Prepare:

- Financial statements
- Excel
- Financial ratios
- Budgeting
- Forecasting
- Financial modeling
- Revenue and expenses
- Profitability
- Valuation basics
- Data analysis

Common questions:

- What are the three major financial statements?
- What is revenue?
- What is profit?
- What is EBITDA?
- What is a financial ratio?
- What is financial forecasting?
- How would you analyze a company's performance?
- How would you identify financial risks?
- How do you use Excel for financial analysis?
- Explain a financial analysis project.

You should be comfortable interpreting numbers and explaining what they
mean for a business.
""",

   
# 27. BANK PO / BANKING
   

"help me in preparation for bank po interview": """
A Bank PO interview commonly evaluates banking awareness, general
knowledge, communication, reasoning, financial concepts, and personality.

Prepare:

- Banking fundamentals
- RBI basics
- Banking services
- Loans
- Deposits
- Interest rates
- Digital banking
- Financial inclusion
- Current economic awareness
- Customer service
- Basic financial terminology

Common questions:

- Why do you want to join banking?
- What does RBI do?
- What is a bank?
- What is a savings account?
- What is a current account?
- What is a loan?
- What is interest?
- What is digital banking?
- What is financial inclusion?
- Why should we select you?

Also prepare questions related to recent economic and banking
developments before the actual interview.
""",

   
# 28. OPERATIONS EXECUTIVE
   

"help me in preparation for operations executive interview": """
An Operations Executive interview focuses on coordination, process
management, efficiency, documentation, communication, and problem
solving.

Prepare:

- Operations management
- Process improvement
- Documentation
- Coordination
- Scheduling
- Reporting
- Excel
- Communication
- Problem solving
- Time management
- Quality control

Common questions:

- What does an Operations Executive do?
- How do you prioritize tasks?
- How do you handle multiple deadlines?
- How would you improve an inefficient process?
- How do you handle operational errors?
- How do you coordinate with different teams?
- How do you maintain accurate records?
- How do you handle pressure?
- How do you track performance?
- Give an example of solving an operational problem.

Be prepared for practical scenario-based questions.
""",

   
# 29. MECHANICAL ENGINEER
   

"help me in preparation for mechanical engineer interview": """
A Mechanical Engineer interview usually tests engineering fundamentals,
problem-solving, practical knowledge, and understanding of mechanical
systems.

Prepare:

- Engineering mechanics
- Thermodynamics
- Fluid mechanics
- Manufacturing
- Materials
- Machine design
- Heat transfer
- CAD basics
- Maintenance
- Safety
- Your engineering projects

Common questions:

- Explain the laws of thermodynamics.
- What is stress and strain?
- What is the difference between heat and temperature?
- What is a bearing?
- What is a gear?
- What is CNC?
- What is CAD?
- What is preventive maintenance?
- How would you troubleshoot a mechanical failure?
- Explain your major engineering project.

Connect theoretical knowledge with practical examples whenever possible.
""",

   
# 30. ELECTRICAL ENGINEER
   

"help me in preparation for electrical engineer interview": """
An Electrical Engineer interview tests electrical fundamentals,
circuits, machines, power systems, control concepts, safety, and
practical troubleshooting.

Prepare:

- Ohm's law
- Kirchhoff's laws
- AC/DC circuits
- Electrical machines
- Transformers
- Motors
- Power systems
- Control systems
- Measurements
- Electronics basics
- Electrical safety
- Engineering projects

Common questions:

- Explain Ohm's law.
- What are Kirchhoff's laws?
- AC vs DC?
- What is a transformer?
- How does an electric motor work?
- What is power factor?
- What is a circuit breaker?
- What is electrical grounding?
- How would you troubleshoot an electrical fault?
- Explain your engineering project.

Be ready to solve basic circuit problems and explain practical
electrical systems clearly.
""", 
# 31. CIVIL ENGINEER 

"help me in preparation for civil engineer interview": """
A Civil Engineer interview tests engineering fundamentals, construction
knowledge, design concepts, materials, surveying, safety, and practical
problem-solving.

Prepare:

- Engineering mechanics
- Strength of materials
- Concrete technology
- Structural engineering basics
- Surveying
- Soil mechanics
- Transportation engineering
- Construction management
- AutoCAD
- Site safety
- Project work

Common questions:

- What is the difference between cement and concrete?
- What is reinforcement in concrete?
- What is a beam and a column?
- What is stress and strain?
- What is surveying?
- What is soil bearing capacity?
- What is curing of concrete?
- What is a foundation?
- What safety precautions are important at a construction site?
- Explain your civil engineering project.

Be ready to connect theoretical concepts with real construction
situations.
""",
 
# 32. ELECTRONICS ENGINEER 

"help me in preparation for electronics engineer interview": """
An Electronics Engineer interview focuses on electronic circuits,
components, digital systems, communication, embedded concepts, and
troubleshooting.

Prepare:

- Analog electronics
- Digital electronics
- Diodes
- Transistors
- Operational amplifiers
- Logic gates
- Microcontrollers
- Communication systems
- Signals
- Sensors
- PCB basics
- Embedded systems

Common questions:

- What is a diode?
- What is a transistor?
- What is an operational amplifier?
- What are logic gates?
- Analog vs digital signals?
- What is a microcontroller?
- What is a sensor?
- What is a PCB?
- How would you troubleshoot an electronic circuit?
- Explain your electronics project.

Practical circuit knowledge and troubleshooting ability can be very
important in electronics interviews.
""",
 
# 33. EMBEDDED SYSTEMS ENGINEER 

"help me in preparation for embedded systems engineer interview": """
An Embedded Systems Engineer interview focuses on programming,
microcontrollers, hardware-software interaction, communication
protocols, and real-time systems.

Prepare:

- C/C++
- Microcontrollers
- Microprocessors
- GPIO
- Interrupts
- Timers
- ADC/DAC
- UART
- SPI
- I2C
- RTOS basics
- Memory
- Sensors
- Debugging

Common questions:

- What is an embedded system?
- Microcontroller vs microprocessor?
- What is an interrupt?
- What is GPIO?
- What is UART?
- SPI vs I2C?
- What is an ADC?
- What is a real-time operating system?
- Why is C commonly used in embedded systems?
- Explain your embedded project.

Be prepared for programming and hardware troubleshooting questions.
""",
 
# 34. NETWORK ENGINEER 

"help me in preparation for network engineer interview": """
A Network Engineer interview focuses on computer networks,
communication protocols, routing, switching, security, and
troubleshooting.

Prepare:

- OSI model
- TCP/IP
- IP addressing
- Subnetting
- DNS
- DHCP
- HTTP/HTTPS
- Routers
- Switches
- VLANs
- Firewalls
- Routing
- Network troubleshooting

Common questions:

- Explain the OSI model.
- TCP vs UDP?
- What is an IP address?
- IPv4 vs IPv6?
- What is DNS?
- What is DHCP?
- What is a router?
- What is a switch?
- What is a VLAN?
- How would you troubleshoot a network connection?

Practice subnetting and practical troubleshooting scenarios.
""",
 
# 35. SYSTEM ADMINISTRATOR 

"help me in preparation for system administrator interview": """
A System Administrator interview focuses on operating systems,
servers, networking, users, security, backups, and troubleshooting.

Prepare:

- Windows/Linux administration
- File systems
- Users and permissions
- Processes
- Services
- Networking
- Servers
- Backups
- Monitoring
- Security
- Command line
- Troubleshooting

Common questions:

- What is an operating system?
- What is a process?
- What is a service?
- How do file permissions work?
- How would you troubleshoot a slow server?
- How would you create a user?
- What is DNS?
- What is a backup?
- How would you recover from a system failure?
- How do you secure a server?

Practical troubleshooting ability is especially important.
""",
 
# 36. UI/UX DESIGNER 

"help me in preparation for ui ux designer interview": """
A UI/UX Designer interview evaluates design thinking, user research,
visual design, usability, prototyping, and problem-solving.

Prepare:

- UI design
- UX principles
- User research
- User personas
- User journeys
- Wireframes
- Prototypes
- Typography
- Color and layout
- Accessibility
- Usability testing
- Figma or similar tools

Common questions:

- What is UI?
- What is UX?
- UI vs UX?
- What is a wireframe?
- What is a prototype?
- How do you conduct user research?
- How do you improve a poor user experience?
- How do you handle design feedback?
- How do you test a design?
- Explain one of your design projects.

Be ready to explain the reasoning behind your design decisions.
""",
 
# 37. GRAPHIC DESIGNER 

"help me in preparation for graphic designer interview": """
A Graphic Designer interview focuses on visual communication,
creativity, design principles, software skills, and portfolio work.

Prepare:

- Typography
- Color theory
- Layout
- Branding
- Composition
- Image editing
- Illustration
- Social media design
- Adobe tools or alternatives
- Portfolio presentation

Common questions:

- What is your design process?
- How do you choose colors?
- How do you choose typography?
- How do you handle client feedback?
- How do you work under deadlines?
- What design tools do you use?
- How do you maintain consistency in branding?
- How do you solve a design problem?
- Which project are you most proud of?
- Explain your portfolio.

Your portfolio is often one of the most important parts of the
interview.
""",
 
# 38. CONTENT WRITER 

"help me in preparation for content writer interview": """
A Content Writer interview evaluates writing ability, research,
grammar, creativity, audience understanding, and content strategy.

Prepare:

- Grammar
- Writing structure
- Research
- Blog writing
- Copywriting
- SEO basics
- Editing
- Proofreading
- Audience analysis
- Content strategy

Common questions:

- Why do you want to become a content writer?
- How do you research a topic?
- How do you write for different audiences?
- What is SEO writing?
- How do you create an engaging headline?
- How do you handle editing feedback?
- How do you ensure factual accuracy?
- How do you meet tight deadlines?
- How do you avoid plagiarism?
- Show us examples of your writing.

A strong writing portfolio can significantly strengthen your application.
""",
 
# 39. SEO SPECIALIST 

"help me in preparation for seo specialist interview": """
An SEO Specialist interview focuses on improving website visibility in
search engines through technical, on-page, and off-page optimization.

Prepare:

- Keyword research
- On-page SEO
- Technical SEO
- Off-page SEO
- Search intent
- Metadata
- Internal linking
- Backlinks
- Site performance
- Analytics
- Search Console
- Content optimization

Common questions:

- What is SEO?
- What is keyword research?
- What is search intent?
- What is on-page SEO?
- What is technical SEO?
- What is a backlink?
- What is internal linking?
- How would you improve a website's search visibility?
- How do you measure SEO performance?
- How would you diagnose a drop in organic traffic?

SEO changes over time, so demonstrate that you understand the need to
keep learning and adapting.
""",
 
# 40. SOCIAL MEDIA MANAGER 

"help me in preparation for social media manager interview": """
A Social Media Manager interview focuses on content strategy, audience
engagement, platform knowledge, analytics, branding, and campaign
management.

Prepare:

- Social media strategy
- Content calendars
- Copywriting
- Audience research
- Community management
- Analytics
- Campaigns
- Branding
- Influencer collaboration
- Crisis communication

Common questions:

- How would you create a social media strategy?
- How do you choose the right platform?
- How do you measure social media success?
- What makes content engaging?
- How would you handle negative comments?
- How do you create a content calendar?
- How would you increase engagement?
- How do you analyze campaign performance?
- How would you promote a new brand?
- Give an example of a successful campaign.

Be ready to discuss both creative ideas and measurable results.
""",
 
# 41. PRODUCT MANAGER 

"help me in preparation for product manager interview": """
A Product Manager interview evaluates product thinking, prioritization,
customer understanding, communication, strategy, and decision-making.

Prepare:

- Product strategy
- User research
- Requirements
- Product roadmaps
- Prioritization
- Metrics
- Stakeholder management
- Agile
- Market research
- Product launches

Common questions:

- What does a Product Manager do?
- How would you prioritize features?
- How do you identify customer needs?
- What makes a good product?
- How would you measure product success?
- How do you handle conflicting stakeholder opinions?
- How would you improve an existing product?
- How would you decide whether to launch a feature?
- What metrics would you track?
- Design a solution for a particular user problem.

Product interviews often test structured thinking rather than one
"correct" answer.
""",
 
# 42. PRODUCT DESIGNER 

"help me in preparation for product designer interview": """
A Product Designer interview combines UX, UI, user research, product
thinking, prototyping, and visual design.

Prepare:

- User research
- Problem definition
- User flows
- Wireframes
- UI design
- Prototyping
- Usability testing
- Design systems
- Accessibility
- Product thinking
- Figma or similar tools

Common questions:

- How do you approach a new design problem?
- How do you understand users?
- What is a user flow?
- How do you prioritize user problems?
- How do you test a design?
- How do you handle conflicting feedback?
- How do you work with developers?
- How do you improve an existing product?
- Explain one product design project.
- Walk us through your design process.

Be prepared to show your portfolio and explain your decisions.
""",
 
# 43. BUSINESS DEVELOPMENT EXECUTIVE 

"help me in preparation for business development executive interview": """
A Business Development Executive interview focuses on finding business
opportunities, generating leads, building relationships, communication,
negotiation, and achieving growth targets.

Prepare:

- Lead generation
- Market research
- Sales
- Customer relationships
- Negotiation
- Communication
- Business proposals
- CRM
- Follow-up
- Target management

Common questions:

- What does business development mean?
- How would you find potential clients?
- How do you generate leads?
- How do you handle rejection?
- How would you approach a new client?
- How do you build long-term relationships?
- How do you negotiate?
- How do you achieve targets?
- How would you identify a new business opportunity?
- Sell this product/service to me.

Practical roleplay is excellent preparation for this position.
""",
 
# 44. RECRUITER / TALENT ACQUISITION 

"help me in preparation for recruiter interview": """
A Recruiter or Talent Acquisition interview focuses on sourcing,
screening, interviewing, communication, candidate experience, and
understanding hiring requirements.

Prepare:

- Recruitment process
- Candidate sourcing
- Job descriptions
- Resume screening
- Interview coordination
- Candidate communication
- LinkedIn/recruitment platforms
- Applicant tracking systems
- Employer branding
- Hiring metrics

Common questions:

- What is recruitment?
- Recruitment vs talent acquisition?
- How do you source candidates?
- How do you screen a resume?
- How do you identify a good candidate?
- How would you handle a difficult candidate?
- How do you manage multiple vacancies?
- How do you improve candidate experience?
- How do you handle confidential candidate information?
- How would you convince a candidate to accept an offer?

Strong communication and organization are essential.
""",
 
# 45. PROCUREMENT EXECUTIVE 

"help me in preparation for procurement executive interview": """
A Procurement Executive interview focuses on purchasing, suppliers,
negotiation, cost management, inventory, documentation, and ensuring
that organizations receive the required goods or services.

Prepare:

- Procurement process
- Supplier management
- Vendor evaluation
- Negotiation
- Purchase orders
- Inventory
- Cost analysis
- Quality
- Documentation
- Contract basics

Common questions:

- What is procurement?
- What is vendor management?
- How do you select a supplier?
- How would you negotiate with a supplier?
- How do you balance cost and quality?
- What is a purchase order?
- How would you handle a delayed supplier?
- How do you evaluate supplier performance?
- How do you prevent procurement errors?
- Describe a difficult negotiation scenario.

Attention to detail and negotiation skills are important.
""",
 
# 46. SUPPLY CHAIN EXECUTIVE 

"help me in preparation for supply chain executive interview": """
A Supply Chain Executive interview focuses on the movement of goods,
inventory, suppliers, logistics, planning, and operational efficiency.

Prepare:

- Supply chain management
- Inventory management
- Procurement
- Warehousing
- Logistics
- Demand planning
- Supplier management
- Cost optimization
- Excel
- Data analysis
- Risk management

Common questions:

- What is supply chain management?
- What is inventory management?
- What is demand forecasting?
- How do you reduce supply chain costs?
- How would you handle a supplier delay?
- What is warehouse management?
- How do you manage inventory shortages?
- How do you evaluate suppliers?
- How would you handle unexpected demand?
- How do you improve supply chain efficiency?

Scenario-based questions are very common in operations roles.
""",
 
# 47. LOGISTICS EXECUTIVE 

"help me in preparation for logistics executive interview": """
A Logistics Executive interview focuses on transportation, shipments,
warehousing, delivery coordination, documentation, and solving
operational problems.

Prepare:

- Transportation
- Warehousing
- Shipment tracking
- Inventory
- Delivery planning
- Documentation
- Vendor coordination
- Cost management
- Route planning
- Customer communication

Common questions:

- What does logistics management involve?
- How would you handle a delayed shipment?
- How do you track deliveries?
- How do you reduce transportation costs?
- What is warehouse management?
- How do you coordinate with transport vendors?
- How would you handle damaged goods?
- How do you prioritize urgent shipments?
- How do you maintain accurate shipment records?
- Describe a logistics problem and how you would solve it.

Organization and quick problem-solving are important.
""",
 
# 48. QUALITY CONTROL / QA EXECUTIVE 

"help me in preparation for quality control executive interview": """
A Quality Control or Quality Assurance Executive interview focuses on
maintaining standards, identifying defects, inspections, documentation,
and process improvement.

Prepare:

- Quality control
- Quality assurance
- Inspection
- Testing
- Defect identification
- Root cause analysis
- Documentation
- Process improvement
- Quality standards
- Audits

Common questions:

- What is quality control?
- What is quality assurance?
- QA vs QC?
- What is a defect?
- What is root cause analysis?
- How would you handle repeated defects?
- How do you maintain quality standards?
- What is an inspection?
- How do you document quality issues?
- How would you improve a defective process?

Be prepared to answer practical quality-control scenarios.
""",
 
# 49. R&D ENGINEER 

"help me in preparation for rd engineer interview": """
An R&D Engineer interview focuses on research, experimentation,
engineering fundamentals, innovation, testing, documentation, and
problem-solving.

Prepare:

- Engineering fundamentals
- Research methodology
- Experiment design
- Prototyping
- Testing
- Data analysis
- Technical documentation
- Problem solving
- Innovation
- Project management

Common questions:

- What does an R&D Engineer do?
- How do you approach an unfamiliar technical problem?
- How do you design an experiment?
- How do you evaluate a prototype?
- How do you analyze experimental results?
- How do you handle failed experiments?
- How do you document technical work?
- How do you improve an existing product?
- How do you research a new technology?
- Explain an engineering project or experiment you worked on.

Curiosity, structured experimentation, and strong technical fundamentals
are valuable for R&D roles.
""",
 
# 50. TECHNICAL SUPPORT ENGINEER 

"help me in preparation for technical support engineer interview": """
A Technical Support Engineer interview combines technical knowledge,
troubleshooting, communication, customer service, and problem-solving.

Prepare:

- Operating systems
- Networking
- Hardware/software basics
- Troubleshooting
- Databases basics
- APIs
- Logs
- Ticketing systems
- Customer communication
- Documentation

Common questions:

- What is technical support?
- How would you troubleshoot a software problem?
- How would you troubleshoot a network issue?
- What is an IP address?
- What is DNS?
- What are logs?
- How do you identify the root cause of an issue?
- How do you handle an angry customer?
- When should an issue be escalated?
- How would you explain a technical problem to a non-technical user?

A strong support engineer should be able to solve technical problems
while communicating clearly with the customer.
""",

# 51. DATA SCIENTIST
"help me in preparation for data scientist interview": """
A Data Scientist interview tests statistical reasoning, coding, machine
learning, and the ability to turn data into useful decisions.

Prepare:
- Probability, statistics, hypothesis testing, and experiment design
- Python or R, SQL, data cleaning, and exploratory analysis
- Supervised and unsupervised learning, evaluation, and feature selection
- Communicating assumptions, uncertainty, and business impact

Common questions:
- How would you investigate a sudden change in a key metric?
- How do you choose a metric and validate an experiment?
- How do you handle missing or imbalanced data?
- Explain a model you built and how you evaluated it.

Practice explaining your reasoning and trade-offs, not just model names.
Use a project example to connect the analysis to an actual decision.
""",

# 52. DATA ENGINEER
"help me in preparation for data engineer interview": """
A Data Engineer interview focuses on building reliable systems that move,
transform, and serve data for analytics and products.

Prepare:
- SQL, Python or Scala, data structures, and query optimization
- ETL/ELT design, batch and streaming pipelines, and orchestration
- Data warehouses, lakehouses, partitioning, and file formats
- Data quality, lineage, access controls, and pipeline monitoring

Common questions:
- How would you design a pipeline for late or duplicated events?
- When would you use batch processing versus streaming?
- How do partitioning and clustering improve query performance?
- How do you detect and recover from a failed pipeline?

Be ready to draw a pipeline, explain failure handling, and quantify its
reliability, cost, and freshness requirements.
""",

# 53. MACHINE LEARNING ENGINEER
"help me in preparation for machine learning engineer interview": """
A Machine Learning Engineer interview combines software engineering with
the practical delivery and maintenance of machine learning systems.

Prepare:
- Python, data structures, APIs, testing, and code quality
- Model training, evaluation, feature pipelines, and reproducibility
- Serving patterns, latency, scaling, and hardware constraints
- Monitoring for drift, failures, fairness, and model performance

Common questions:
- How would you move a notebook model into production?
- How do you prevent training-serving skew?
- What would you monitor after deploying a model?
- How would you reduce inference latency or cost?

Describe the full lifecycle of a model you worked on, including the
engineering choices and what you would improve next.
""",

# 54. AI ENGINEER
"help me in preparation for ai engineer interview": """
An AI Engineer interview tests your ability to build useful AI features,
integrate models, and make them dependable for real users.

Prepare:
- Python, APIs, model inference, and application architecture
- Prompting, retrieval-augmented generation, embeddings, and evaluation
- Data preparation, privacy, security, and responsible AI practices
- Latency, cost, reliability, fallback behavior, and user experience

Common questions:
- How would you ground an AI answer in trusted documents?
- How do you evaluate quality when answers can vary?
- How would you handle incorrect output or prompt injection?
- How do you balance response quality, latency, and cost?

Explain how you would test the complete feature, including edge cases,
human review, and a safe fallback when the model is uncertain.
""",

# 55. BUSINESS INTELLIGENCE ANALYST
"help me in preparation for business intelligence analyst interview": """
A Business Intelligence Analyst interview focuses on reliable reporting,
metric definitions, and explaining business performance through data.

Prepare:
- SQL joins, aggregations, window functions, and data validation
- Dashboard design and a BI tool such as Power BI or Tableau
- Data models, KPIs, reporting cadence, and stakeholder requirements
- Clear communication of trends, caveats, and recommended actions

Common questions:
- How would you define and validate a business KPI?
- How do you investigate two reports showing different totals?
- What makes a dashboard useful to an executive?
- Describe an insight that changed a team's decision.

Use examples that show how you checked the numbers and made the result
easy for a non-technical audience to act on.
""",

# 56. DATABASE ADMINISTRATOR
"help me in preparation for database administrator interview": """
A Database Administrator interview tests database reliability,
performance, security, backup, and recovery skills.

Prepare:
- Relational database concepts, SQL, indexing, and query plans
- Backups, point-in-time recovery, replication, and disaster recovery
- Access control, encryption, patching, and audit practices
- Capacity planning, performance monitoring, and incident response

Common questions:
- How would you diagnose a slow query or overloaded database?
- How do you verify that backups can actually be restored?
- What is the purpose of replication, and what can go wrong?
- How would you respond to accidental data deletion?

Describe the safeguards and recovery steps you would use before making
high-impact changes to a production database.
""",

# 57. DATABASE DEVELOPER
"help me in preparation for database developer interview": """
A Database Developer interview focuses on designing data structures and
writing efficient, maintainable database logic.

Prepare:
- SQL queries, joins, subqueries, CTEs, and window functions
- Schema design, normalization, constraints, and data types
- Stored procedures, transactions, indexes, and query optimization
- Data migrations, testing, and application-database integration

Common questions:
- How would you model a many-to-many relationship?
- When can an index make performance worse?
- How do transactions and isolation levels affect concurrent work?
- How would you safely migrate a large table?

Practice writing SQL aloud, checking edge cases, and explaining why your
schema supports the application's access patterns.
""",

# 58. SOLUTIONS ARCHITECT
"help me in preparation for solutions architect interview": """
A Solutions Architect interview evaluates how you translate business and
technical needs into secure, scalable, supportable system designs.

Prepare:
- Requirements discovery, architecture diagrams, and design trade-offs
- Cloud networking, compute, storage, identity, and observability
- Security, resilience, performance, migration, and cost management
- Stakeholder communication and phased implementation planning

Common questions:
- Design a highly available service for a growing customer base.
- How would you migrate a legacy application to the cloud?
- How do you choose between managed services and custom components?
- How would you explain a costly design trade-off to a client?

Start by clarifying constraints and service goals, then explain options,
risks, and why your recommendation fits the requirements.
""",

# 59. SOFTWARE ARCHITECT
"help me in preparation for software architect interview": """
A Software Architect interview tests system design, technical judgment,
and the ability to guide teams toward maintainable software.

Prepare:
- Component boundaries, APIs, data ownership, and design patterns
- Scalability, reliability, security, and performance trade-offs
- Modernization, technical debt, and incremental migration strategies
- Architecture documentation and collaboration with engineering teams

Common questions:
- How would you split a large application into clear components?
- When would you choose a monolith over microservices?
- How do you handle a design disagreement across teams?
- Describe an architecture decision you later changed.

Use concrete examples and explain the constraints behind each decision;
avoid presenting any one architecture style as right for every system.
""",

# 60. QA AUTOMATION ENGINEER
"help me in preparation for qa automation engineer interview": """
A QA Automation Engineer interview evaluates test design, automation
skills, and how you improve confidence without slowing delivery.

Prepare:
- Testing fundamentals, risk-based coverage, and test case design
- UI, API, and integration automation with a relevant language/tool
- CI pipelines, test data, mocks, and environment management
- Debugging flaky tests, reporting defects, and preventing regressions

Common questions:
- What belongs in unit, integration, and end-to-end tests?
- How would you investigate a test that fails intermittently?
- How do you choose what should be automated?
- How would you test an API with changing or missing data?

Show how your tests catch meaningful defects and how you keep the suite
fast, stable, and useful to developers.
""",

# 61. SITE RELIABILITY ENGINEER
"help me in preparation for site reliability engineer interview": """
A Site Reliability Engineer interview focuses on keeping services reliable
through engineering, automation, and disciplined incident response.

Prepare:
- Linux, networking, scripting, distributed systems, and cloud platforms
- SLIs, SLOs, error budgets, alert quality, and capacity planning
- Observability, incident command, postmortems, and toil reduction
- Deployment safety, resilience testing, and automation

Common questions:
- How would you respond to a service-wide latency spike?
- What makes an alert actionable?
- How do SLOs and error budgets guide release decisions?
- How would you reduce recurring operational toil?

Structure incident answers around impact, stabilization, communication,
root cause, and follow-up actions that prevent recurrence.
""",

# 62. BLOCKCHAIN DEVELOPER
"help me in preparation for blockchain developer interview": """
A Blockchain Developer interview tests smart contract development,
distributed ledger concepts, and secure handling of digital assets.

Prepare:
- Solidity or the chain's relevant language, testing, and deployment
- Transactions, consensus, wallets, keys, and contract interaction
- Gas costs, access control, upgrade patterns, and common vulnerabilities
- Events, indexing, APIs, and integration with regular applications

Common questions:
- What makes a smart contract transaction irreversible?
- How would you prevent reentrancy or unauthorized access?
- How do you test contracts before mainnet deployment?
- When is a blockchain unnecessary for a product?

Emphasize threat modeling and independent review; a small contract bug
can have permanent financial consequences.
""",

# 63. GAME DEVELOPER
"help me in preparation for game developer interview": """
A Game Developer interview evaluates programming fundamentals, gameplay
systems, performance awareness, and collaboration with creative teams.

Prepare:
- C# or C++, object-oriented design, and data structures
- Game loops, physics, input, animation, and state management
- Profiling, memory use, frame time, and platform constraints
- Version control, debugging, and working with artists and designers

Common questions:
- How would you implement a reusable player ability system?
- How do you find and fix a frame-rate bottleneck?
- What is the difference between update and fixed update loops?
- Explain a game feature you built and the trade-offs involved.

Bring a playable project or code sample if possible, and be ready to
explain your personal contribution clearly.
""",

# 64. IOS DEVELOPER
"help me in preparation for ios developer interview": """
An iOS Developer interview tests Swift knowledge and your ability to build
responsive, reliable apps that fit Apple's platform conventions.

Prepare:
- Swift, optionals, value/reference types, and concurrency
- UIKit or SwiftUI, navigation, layout, and accessibility
- Networking, persistence, caching, and offline behavior
- App lifecycle, memory management, testing, and release processes

Common questions:
- How do Swift structs differ from classes?
- How do you handle asynchronous network requests safely?
- How would you diagnose a memory leak or slow screen?
- How do you protect credentials and sensitive local data?

Explain an app feature from UI through data flow, error handling, and
testing on different device sizes.
""",

# 65. ANDROID DEVELOPER
"help me in preparation for android developer interview": """
An Android Developer interview evaluates Kotlin or Java skills and your
understanding of the Android app lifecycle and device ecosystem.

Prepare:
- Kotlin, coroutines, collections, and object-oriented fundamentals
- Activities, lifecycle, Jetpack components, and UI architecture
- Networking, persistence, background work, and offline behavior
- Testing, accessibility, performance, and app security

Common questions:
- What happens during an activity lifecycle change?
- How do coroutines help manage asynchronous work?
- How would you prevent data loss when a process is killed?
- How do you investigate a crash seen only on some devices?

Discuss how you handle lifecycle changes, poor connectivity, and the wide
range of Android devices in real-world use.
""",

# 66. SALESFORCE DEVELOPER
"help me in preparation for salesforce developer interview": """
A Salesforce Developer interview tests platform development, data
modeling, automation, and safe customization of Salesforce applications.

Prepare:
- Apex, SOQL, triggers, governor limits, and asynchronous jobs
- Lightning Web Components, events, and user interface patterns
- Objects, relationships, flows, profiles, and permission sets
- Bulk-safe code, testing, deployments, and integration APIs

Common questions:
- What are governor limits, and how do you design around them?
- How do you avoid recursion and bulkification issues in triggers?
- When would you use Flow instead of Apex?
- How do you deploy changes safely across environments?

Show that you can choose declarative tools when suitable and write
maintainable code when platform automation needs it.
""",

# 67. SAP CONSULTANT
"help me in preparation for sap consultant interview": """
An SAP Consultant interview focuses on business processes, SAP module
knowledge, configuration, and translating requirements into solutions.

Prepare:
- The target module and its end-to-end business processes
- Requirements workshops, fit-gap analysis, and configuration choices
- Master data, integrations, testing, and change management
- Issue triage, documentation, and user training

Common questions:
- How do you gather requirements from conflicting stakeholders?
- Explain a process you configured from start to finish.
- How do you approach a gap between standard SAP and a request?
- How would you plan testing for a major process change?

Name the SAP module and project scope you know best; connect each
configuration decision to the business outcome it supports.
""",

# 68. ROBOTICS ENGINEER
"help me in preparation for robotics engineer interview": """
A Robotics Engineer interview tests your understanding of software,
hardware, sensing, and control working together in physical systems.

Prepare:
- C++ or Python, ROS, Linux, and real-time considerations
- Kinematics, control systems, sensors, and actuator behavior
- Localization, mapping, path planning, and perception basics
- Simulation, hardware testing, safety, and fault handling

Common questions:
- How would you localize a robot with noisy sensor readings?
- What is the difference between open- and closed-loop control?
- How would you debug a robot that behaves differently on hardware?
- How do you make motion safe around people?

Use a project example to explain sensor inputs, control decisions,
failure modes, and how you validated behavior in the real world.
""",

# 69. HARDWARE ENGINEER
"help me in preparation for hardware engineer interview": """
A Hardware Engineer interview evaluates circuit knowledge, design
validation, debugging, and awareness of manufacturing constraints.

Prepare:
- Analog and digital circuits, components, and signal integrity
- Schematics, PCB layout concepts, and measurement instruments
- Simulation, prototyping, design verification, and documentation
- Power, thermal, reliability, cost, and compliance considerations

Common questions:
- How would you debug a board that fails intermittently?
- How do component tolerances affect circuit behavior?
- What checks do you perform before releasing a PCB design?
- Describe a design trade-off you made under a cost constraint.

Explain your methodical test process and how you separate a design
issue from a manufacturing or measurement problem.
""",

# 70. IT SUPPORT SPECIALIST
"help me in preparation for it support specialist interview": """
An IT Support Specialist interview tests practical troubleshooting,
customer service, and the ability to restore users' productivity.

Prepare:
- Windows or macOS basics, accounts, permissions, and endpoint tools
- Networking fundamentals, printers, collaboration, and common apps
- Ticket prioritization, documentation, escalation, and follow-up
- Security awareness, phishing response, and safe remote support

Common questions:
- How would you troubleshoot a user who cannot sign in?
- How do you prioritize several urgent support tickets?
- What would you do if you suspected a phishing incident?
- How do you explain a technical fix to a frustrated user?

Answer with a calm, repeatable process: clarify impact, check basics,
protect the user, document the fix, and confirm resolution.
""",

# 71. INVESTMENT BANKER
"help me in preparation for investment banker interview": """
An Investment Banker interview tests financial modeling, accounting,
valuation, commercial judgment, and performance under pressure.

Prepare:
- Financial statements and links between them
- DCF, comparable companies, precedent transactions, and multiples
- M&A rationale, deal process, diligence, and financing basics
- Current market themes and the bank's recent sector activity

Common questions:
- Walk me through a discounted cash flow valuation.
- How does a change in depreciation affect the statements?
- What makes a merger financially attractive?
- Pitch a company or discuss a recent transaction.

Practice concise mental math and structured explanations. Be specific
about why this role, team, and market interest you.
""",

# 72. EQUITY RESEARCH ANALYST
"help me in preparation for equity research analyst interview": """
An Equity Research Analyst interview assesses financial analysis,
valuation, industry understanding, and the clarity of an investment view.

Prepare:
- Financial statement analysis, forecasting, and valuation methods
- Industry structure, competitive advantages, and key drivers
- Earnings, catalysts, risks, and sensitivity analysis
- Clear written and verbal investment recommendations

Common questions:
- Pitch a stock and explain your thesis and downside risks.
- Which assumptions matter most in your valuation?
- How would you evaluate a company with negative earnings?
- What changed in a recent company result or industry trend?

Support your view with evidence and a valuation range; discuss what
would prove your thesis wrong as well as what could make it work.
""",

# 73. CREDIT ANALYST
"help me in preparation for credit analyst interview": """
A Credit Analyst interview focuses on a borrower's ability and willingness
to repay, with careful analysis of risk and cash flow.

Prepare:
- Financial statements, leverage, liquidity, and cash flow analysis
- Credit ratios, covenants, collateral, and repayment structures
- Industry and borrower risks, sensitivity analysis, and rating rationale
- Clear credit memos and policy-compliant recommendations

Common questions:
- How would you assess a company's capacity to service debt?
- What warning signs might appear before a default?
- How do covenants reduce lender risk?
- What would you do if financial results deteriorated after approval?

Separate facts from assumptions and explain how downside scenarios
change your recommendation and proposed protections.
""",

# 74. RISK ANALYST
"help me in preparation for risk analyst interview": """
A Risk Analyst interview tests how you identify, measure, and communicate
uncertainty so an organization can make informed decisions.

Prepare:
- Risk identification, assessment, controls, and reporting
- Quantitative analysis, scenarios, stress tests, and data quality
- Relevant operational, financial, market, or compliance risks
- Risk appetite, escalation, governance, and mitigation plans

Common questions:
- How would you rank risks with limited data?
- What is the difference between inherent and residual risk?
- How would you test whether a control is effective?
- Describe a risk you surfaced and how stakeholders responded.

Be clear about probability, impact, assumptions, and owners; a useful
analysis ends with practical actions and monitoring signals.
""",

# 75. INTERNAL AUDITOR
"help me in preparation for internal auditor interview": """
An Internal Auditor interview evaluates control testing, evidence-based
judgment, process understanding, and professional communication.

Prepare:
- Risk-based audit planning, walkthroughs, sampling, and documentation
- Internal controls, segregation of duties, and compliance requirements
- Evidence evaluation, root-cause analysis, and issue rating
- Clear findings, recommendations, and follow-up testing

Common questions:
- How do you test whether a control is operating effectively?
- What would you do if evidence is incomplete or contradictory?
- How do you communicate a finding that a process owner disputes?
- How do you prioritize audit coverage?

Use examples that show independence and fairness: validate facts,
understand the root cause, and make recommendations practical.
""",

# 76. TAX CONSULTANT
"help me in preparation for tax consultant interview": """
A Tax Consultant interview tests technical tax knowledge, research,
accuracy, client service, and the ability to explain obligations clearly.

Prepare:
- The relevant jurisdiction's individual or corporate tax framework
- Return preparation, tax research, reconciliations, and documentation
- Compliance calendars, deductions, credits, and common risk areas
- Confidentiality, ethics, and communication with clients

Common questions:
- How do you research a tax question with unclear facts?
- What checks help prevent errors in a return?
- How would you explain a tax adjustment to a client?
- What would you do after identifying a prior filing error?

Tax rules vary by jurisdiction and change over time; state the facts and
period you are discussing, and explain how you verify current guidance.
""",

# 77. ACTUARY
"help me in preparation for actuary interview": """
An Actuary interview evaluates quantitative reasoning and the use of
statistical models to measure financial risk over time.

Prepare:
- Probability, statistics, survival models, and time value of money
- Pricing, reserving, forecasting, and sensitivity analysis
- Excel and relevant programming or actuarial modeling tools
- Assumptions, uncertainty, regulation, and clear stakeholder reporting

Common questions:
- How would you estimate the expected cost of a claim portfolio?
- How do assumptions affect a reserve estimate?
- How would you explain model uncertainty to a business leader?
- Describe a quantitative analysis you built and validated.

Show careful reasoning and validation habits, and connect the model's
limitations to the decision it is intended to support.
""",

# 78. CHARTERED ACCOUNTANT
"help me in preparation for chartered accountant interview": """
A Chartered Accountant interview may cover audit, accounting, tax,
financial reporting, controls, and advisory work.

Prepare:
- Financial statements, accounting standards, and reconciliations
- Audit planning, evidence, materiality, and internal controls
- Tax compliance and research for the relevant jurisdiction
- Ethics, client communication, and deadlines during busy periods

Common questions:
- How do you assess materiality and audit risk?
- What would you do after finding a significant misstatement?
- How do you manage competing client deadlines?
- Describe a difficult accounting issue you researched.

Clarify which area and jurisdiction the role covers, then use examples
from articleship, audit, finance, or client assignments.
""",

# 79. TREASURY ANALYST
"help me in preparation for treasury analyst interview": """
A Treasury Analyst interview focuses on cash visibility, liquidity,
forecasting, funding, and financial risk management.

Prepare:
- Cash flow forecasting, bank reconciliations, and liquidity reporting
- Debt, investments, foreign exchange, and interest rate basics
- Treasury systems, controls, approvals, and payment operations
- Scenario analysis and communication with finance partners

Common questions:
- How would you improve the accuracy of a cash forecast?
- What risks arise from holding cash in multiple currencies?
- How do you investigate an unexpected bank reconciliation item?
- How would you maintain controls over payments?

Highlight accuracy and control discipline alongside analytical skills;
treasury decisions affect both daily operations and financial exposure.
""",

# 80. PAYROLL SPECIALIST
"help me in preparation for payroll specialist interview": """
A Payroll Specialist interview tests payroll accuracy, confidentiality,
employee service, and compliance with local rules and deadlines.

Prepare:
- Payroll cycles, deductions, benefits, leave, and reconciliations
- HRIS or payroll systems, data validation, and audit trails
- Tax and labor requirements relevant to the location
- Handling corrections, sensitive data, and employee questions

Common questions:
- How would you investigate an employee's incorrect pay?
- What checks do you run before finalizing payroll?
- How do you protect confidential payroll information?
- What would you do if a required input arrives after cutoff?

Emphasize a documented review process and careful handling of personal
data; explain how you meet deadlines without skipping controls.
""",

# 81. MARKETING MANAGER
"help me in preparation for marketing manager interview": """
A Marketing Manager interview evaluates strategy, customer insight,
campaign execution, measurement, and team leadership.

Prepare:
- Audience segmentation, positioning, messaging, and channel selection
- Campaign budgets, calendars, creative review, and execution
- KPIs, attribution limits, experimentation, and optimization
- Cross-functional work with sales, product, and creative teams

Common questions:
- How would you launch a product with a limited budget?
- Which metrics show whether a campaign is working?
- How do you resolve disagreement over campaign priorities?
- Describe a campaign you improved using performance data.

Bring a measurable example and distinguish activity metrics from the
business outcomes the campaign was meant to influence.
""",

# 82. BRAND MANAGER
"help me in preparation for brand manager interview": """
A Brand Manager interview tests brand positioning, consumer insight,
creative judgment, and commercial performance.

Prepare:
- Brand purpose, target audience, differentiation, and consistency
- Research, campaign briefs, creative evaluation, and channel plans
- Market share, awareness, consideration, and sales performance
- Budget management and collaboration with agencies and product teams

Common questions:
- How would you reposition a brand losing relevance?
- How do you measure brand health beyond short-term sales?
- How would you brief an agency on a new campaign?
- Describe a brand decision you made using customer insight.

Show how you balance long-term brand equity with near-term commercial
goals, supported by a clear audience and evidence.
""",

# 83. MARKET RESEARCH ANALYST
"help me in preparation for market research analyst interview": """
A Market Research Analyst interview focuses on designing sound research,
analyzing markets, and turning findings into useful recommendations.

Prepare:
- Survey design, sampling, interviews, and research ethics
- Quantitative analysis, qualitative coding, and data visualization
- Competitor, customer, and market sizing research
- Clear summaries that separate evidence from interpretation

Common questions:
- How would you estimate demand for a new product?
- How do you reduce bias in a survey or interview study?
- When would you choose qualitative over quantitative research?
- How would you present conflicting research findings?

Explain your method and its limitations. Strong recommendations depend
on representative evidence, not just a large-looking dataset.
""",

# 84. PERFORMANCE MARKETING SPECIALIST
"help me in preparation for performance marketing specialist interview": """
A Performance Marketing Specialist interview tests paid campaign
execution, measurement, and disciplined optimization.

Prepare:
- Search, social, display, or affiliate platforms relevant to the role
- Tracking plans, pixels, conversion events, and attribution caveats
- Budget pacing, bidding, audience tests, and creative experiments
- CAC, ROAS, conversion rate, and funnel analysis

Common questions:
- What would you check if spend rises but conversions fall?
- How would you structure an experiment for new ad creative?
- How do you validate conversion tracking?
- When would you pause or scale a campaign?

Use numbers from a campaign you know and explain how you separated
seasonality, tracking issues, and real performance changes.
""",

# 85. EMAIL MARKETING SPECIALIST
"help me in preparation for email marketing specialist interview": """
An Email Marketing Specialist interview evaluates lifecycle strategy,
audience segmentation, deliverability, and campaign measurement.

Prepare:
- Segments, journeys, triggers, personalization, and consent practices
- Subject lines, content design, accessibility, and calls to action
- Deliverability, list hygiene, bounce rates, and unsubscribe handling
- A/B testing and metrics such as clicks and downstream conversions

Common questions:
- How would you improve engagement in an inactive segment?
- What would you test in a welcome email journey?
- How do you protect deliverability and subscriber trust?
- How do you measure email's contribution to a conversion?

Show that you optimize for useful customer experiences and long-term
list health, not opens or send volume alone.
""",

# 86. PUBLIC RELATIONS MANAGER
"help me in preparation for public relations manager interview": """
A Public Relations Manager interview tests storytelling, media judgment,
stakeholder management, and preparation for sensitive situations.

Prepare:
- Messaging, press materials, spokesperson preparation, and media lists
- Media monitoring, coverage analysis, and reputation management
- Crisis planning, approvals, accuracy, and timely communication
- Relationships with executives, legal teams, and external partners

Common questions:
- How would you respond to a fast-moving negative story?
- How do you measure PR impact beyond media mentions?
- How would you prepare an executive for a difficult interview?
- Describe a communications issue you handled under pressure.

In scenario answers, establish verified facts, audiences, approvals,
and a clear response plan before speculating publicly.
""",

# 87. EVENT MANAGER
"help me in preparation for event manager interview": """
An Event Manager interview focuses on planning, logistics, suppliers,
budgets, attendee experience, and handling live issues.

Prepare:
- Event briefs, timelines, run-of-show plans, and contingency plans
- Venue, vendor, travel, registration, and accessibility coordination
- Budget tracking, contracts, safety, and permits as applicable
- Attendee communications and post-event measurement

Common questions:
- What would you do if a key supplier cancelled on event day?
- How do you keep an event on budget as requirements change?
- How do you plan for safety and accessibility?
- How do you evaluate whether an event achieved its goals?

Use a specific event example and explain how you managed dependencies,
communicated changes, and protected the attendee experience.
""",

# 88. CUSTOMER SUCCESS MANAGER
"help me in preparation for customer success manager interview": """
A Customer Success Manager interview tests relationship building,
customer outcomes, retention, and proactive account management.

Prepare:
- Onboarding, adoption plans, success metrics, and renewal readiness
- Discovery, executive business reviews, and stakeholder mapping
- Risk signals, escalation, product feedback, and cross-team coordination
- Clear communication when customer expectations exceed product scope

Common questions:
- How would you re-engage a customer with low product adoption?
- What signals suggest an account is at risk of churn?
- How do you turn customer goals into an adoption plan?
- Describe a renewal you helped secure or improve.

Center the answer on measurable customer value and a practical action
plan, while setting honest expectations about what the product can do.
""",

# 89. ACCOUNT EXECUTIVE
"help me in preparation for account executive interview": """
An Account Executive interview evaluates discovery, solution selling,
pipeline discipline, negotiation, and closing skills.

Prepare:
- Prospect qualification, discovery questions, and decision processes
- Product positioning, demonstrations, objection handling, and proposals
- Forecasting, CRM hygiene, deal strategy, and territory planning
- Ethical negotiation and handoff to implementation or customer success

Common questions:
- How do you qualify a prospect with competing priorities?
- How would you respond to a price objection?
- Walk me through a complex deal you won or lost.
- How do you keep a forecast accurate?

Use specific results and explain your contribution, sales cycle, and
learning; avoid taking credit for outcomes you did not control.
""",

# 90. KEY ACCOUNT MANAGER
"help me in preparation for key account manager interview": """
A Key Account Manager interview focuses on retaining and growing
strategic customer relationships over the long term.

Prepare:
- Account plans, stakeholder maps, business reviews, and growth targets
- Negotiation, commercial agreements, renewals, and issue resolution
- Customer health, risks, opportunities, and internal coordination
- Product, service, and financial knowledge for your customer segment

Common questions:
- How would you grow a mature account without damaging trust?
- How do you handle a strategic customer escalation?
- How do you prioritize accounts with different needs?
- Describe how you recovered or expanded an important relationship.

Show a balance of customer advocacy and commercial judgment, backed by
clear account outcomes and a thoughtful communication cadence.
""",

# 91. LEARNING AND DEVELOPMENT SPECIALIST
"help me in preparation for learning and development specialist interview": """
A Learning and Development Specialist interview tests learning design,
facilitation, needs analysis, and evidence of skill improvement.

Prepare:
- Training needs assessment and measurable learning objectives
- Course design, facilitation, coaching, and accessible materials
- Learning platforms, feedback, assessment, and program evaluation
- Stakeholder alignment, scheduling, and continuous improvement

Common questions:
- How would you determine whether a team needs training?
- How do you measure learning transfer on the job?
- How would you adapt a session for different experience levels?
- Describe a program you designed and how you improved it.

Connect learning activities to job performance, and use evaluation
methods that go beyond attendance or participant satisfaction.
""",

# 92. COMPENSATION AND BENEFITS ANALYST
"help me in preparation for compensation and benefits analyst interview": """
A Compensation and Benefits Analyst interview focuses on pay analysis,
benefit programs, data accuracy, and fair, consistent administration.

Prepare:
- Job evaluation, salary ranges, market benchmarks, and pay structures
- Benefits plan basics, enrollment, vendor coordination, and reporting
- Excel or HR analytics, confidentiality, and data validation
- Internal equity, policy interpretation, and relevant local requirements

Common questions:
- How would you assess whether a salary range is competitive?
- What checks would you perform on compensation data?
- How do you explain a benefits change to employees?
- How would you handle a sensitive pay equity finding?

Demonstrate discretion and analytical care; explain assumptions and
protect individual employee information throughout your work.
""",

# 93. SCRUM MASTER
"help me in preparation for scrum master interview": """
A Scrum Master interview tests facilitation, servant leadership, and
your ability to help a team improve its delivery system.

Prepare:
- Scrum events, artifacts, roles, and practical agile principles
- Removing blockers, coaching, team health, and continuous improvement
- Backlog collaboration, estimation, dependencies, and transparency
- Handling conflict without taking ownership away from the team

Common questions:
- What would you do when a team repeatedly misses its sprint goal?
- How do you handle an urgent request during a sprint?
- How do you help a team surface an unresolved conflict?
- Which signals show that a team is improving?

Describe how you enable the team to solve problems; avoid treating
ceremonies or velocity as the goal by themselves.
""",

# 94. PROGRAM MANAGER
"help me in preparation for program manager interview": """
A Program Manager interview evaluates coordination across related
projects, strategic outcomes, dependencies, and executive communication.

Prepare:
- Program goals, roadmaps, milestones, dependencies, and governance
- Risk and issue management across multiple teams
- Resource planning, decision tracking, and outcome measurement
- Clear status updates tailored to executives and delivery teams

Common questions:
- How would you recover a program with several delayed workstreams?
- How do you surface cross-team dependencies early?
- How do you measure program outcomes after launch?
- Describe a difficult trade-off you aligned stakeholders around.

Explain how you create visibility and help owners make decisions without
turning the program into status reporting alone.
""",

# 95. IT PROJECT MANAGER
"help me in preparation for it project manager interview": """
An IT Project Manager interview tests delivery planning, stakeholder
alignment, technical awareness, risk control, and change management.

Prepare:
- Scope, schedules, budgets, dependencies, and delivery methods
- Requirements, change control, risks, issues, and decision logs
- Coordination with engineering, security, vendors, and business teams
- Testing, cutover, training, and post-launch support planning

Common questions:
- How do you handle a late change to a fixed-scope project?
- What would you do when a critical dependency slips?
- How do you communicate technical risk to a sponsor?
- Describe a project that missed a target and what you learned.

Use a real project example with your role, constraints, actions, and
measurable result; be candid about lessons from setbacks.
""",

# 96. CONSTRUCTION PROJECT MANAGER
"help me in preparation for construction project manager interview": """
A Construction Project Manager interview focuses on safe, coordinated
delivery across design, contractors, budgets, schedules, and site work.

Prepare:
- Scope, drawings, schedules, procurement, and subcontractor coordination
- Cost tracking, change orders, progress claims, and contract basics
- Site safety, quality inspections, permits, and regulatory requirements
- Risk logs, issue escalation, and client or community communication

Common questions:
- How would you manage a delay caused by a critical subcontractor?
- What steps do you take when site work differs from drawings?
- How do you balance schedule pressure with safety requirements?
- Describe how you controlled scope or cost on a project.

Frame examples around safety, documented decisions, and early
communication with the people responsible for each workstream.
""",

# 97. ARCHITECT
"help me in preparation for architect interview": """
An Architect interview evaluates design thinking, technical coordination,
code awareness, client communication, and the quality of your portfolio.

Prepare:
- Concept development, space planning, drawings, and design rationale
- Building systems, materials, accessibility, and local code coordination
- BIM or CAD tools, consultant collaboration, and drawing reviews
- Project stages, client feedback, sustainability, and constructability

Common questions:
- Walk us through a project from brief to developed design.
- How did you respond to a client changing requirements?
- How do you balance design intent with budget and code constraints?
- What would you revise in a project in your portfolio?

Choose portfolio work you can explain deeply, including your own role,
constraints, design iterations, and lessons from coordination.
""",

# 98. INTERIOR DESIGNER
"help me in preparation for interior designer interview": """
An Interior Designer interview tests space planning, material choices,
technical detailing, client service, and design presentation.

Prepare:
- User needs, circulation, ergonomics, lighting, and spatial layouts
- Materials, finishes, furniture, specifications, and sustainability
- CAD or BIM tools, schedules, budgets, and vendor coordination
- Codes, accessibility, site review, and design revisions

Common questions:
- How do you turn a client's preferences into a coherent concept?
- How do you choose finishes within a strict budget?
- How do you coordinate drawings with contractors and suppliers?
- Describe a design change you made after client or site feedback.

Use a portfolio example to show both the visual concept and the
practical details that made it buildable and usable.
""",

# 99. TEACHER
"help me in preparation for teacher interview": """
A Teacher interview focuses on subject knowledge, inclusive instruction,
classroom practice, assessment, and student wellbeing.

Prepare:
- Lesson planning, learning objectives, differentiation, and pacing
- Classroom routines, behavior support, and safe learning environments
- Formative assessment, feedback, and use of student progress data
- Family communication, collaboration, and safeguarding procedures

Common questions:
- How do you support students with different learning needs?
- What would you do if a lesson is not engaging the class?
- How do you assess whether students understood a concept?
- Describe how you handled a challenging classroom situation.

Use specific examples and explain how you reflect on evidence and
adjust instruction while keeping student safety and dignity central.
""",

# 100. REGISTERED NURSE
"help me in preparation for registered nurse interview": """
A Registered Nurse interview evaluates clinical judgment, patient safety,
communication, teamwork, and compassionate care.

Prepare:
- Assessment, prioritization, documentation, and escalation of concerns
- Infection prevention, medication safety, and relevant clinical protocols
- Patient education, consent, confidentiality, and family communication
- Team handoffs, workload management, and reflective practice

Common questions:
- What would you do if a patient's condition suddenly changed?
- How do you prioritize several patients with competing needs?
- How would you respond to a medication error or near miss?
- Describe a difficult interaction with a patient or colleague.

Answer scenario questions with patient safety first, clear escalation,
accurate documentation, and respect for local clinical protocols.
""",

# 101. UX RESEARCHER
"help me in preparation for ux researcher interview": """
A UX Researcher interview tests how you plan studies, understand user needs,
and turn evidence into decisions for a product team.

Prepare:
- Research questions, method selection, recruiting, and consent
- Interviews, usability tests, surveys, and mixed-method analysis
- Bias, accessibility, synthesis, and communicating limitations
- Connecting findings to product decisions without overstating evidence

Common questions:
- How would you choose between interviews and a usability test?
- What would you do if research findings conflict with stakeholder views?
- How do you reduce bias in a study?
- Describe a finding that changed a product decision.

Explain the question, method, evidence, and resulting decision for each
example; protect participant privacy and be candid about limitations.
""",

# 102. TECHNICAL WRITER
"help me in preparation for technical writer interview": """
A Technical Writer interview evaluates clear writing, information design,
and the ability to work with subject-matter experts.

Prepare:
- Audience analysis, task-based documentation, and information architecture
- Editing, style guides, accessibility, and plain-language writing
- Docs-as-code, version control, content review, and release workflows
- API references, tutorials, troubleshooting, or product docs relevant to the role

Common questions:
- How do you explain a complex feature to a new user?
- How do you validate technical accuracy with an expert?
- How do you keep documentation aligned with product changes?
- Walk through a sample in your writing portfolio.

Bring work samples if available and explain your process from research
through review, publication, and feedback-driven revision.
""",

# 103. LAWYER
"help me in preparation for lawyer interview": """
A Lawyer interview may assess legal analysis, research, drafting, ethics,
and communication with clients or colleagues.

Prepare:
- The practice area and jurisdiction relevant to the position
- Issue spotting, legal research, writing, and argument structure
- Client interviewing, confidentiality, conflicts, and professional ethics
- Managing deadlines, evidence, and changing facts

Common questions:
- How would you analyze a question with incomplete facts?
- How do you verify that a legal source is current and relevant?
- How would you explain legal options to a non-lawyer?
- Describe a time you handled competing deadlines or feedback.

Keep scenario answers jurisdiction-aware, protect confidentiality, and
show how you distinguish known facts from assumptions.
""",

# 104. PHARMACIST
"help me in preparation for pharmacist interview": """
A Pharmacist interview evaluates medication knowledge, patient safety,
accuracy, and clear communication with patients and care teams.

Prepare:
- Prescription review, dosing, interactions, allergies, and counseling
- Dispensing accuracy, inventory, documentation, and quality checks
- Relevant local pharmacy rules, privacy, and controlled medicines
- Communicating concerns and escalating clinical risks appropriately

Common questions:
- What would you do if you identified a potentially harmful interaction?
- How do you counsel a patient who is unsure about a medication?
- How do you reduce dispensing errors during a busy shift?
- Describe how you handled a difficult patient-care situation.

Prioritize patient safety, clarify the facts, and follow the applicable
clinical protocols and local professional requirements.
""",

# 105. PHYSICIAN
"help me in preparation for physician interview": """
A Physician interview assesses clinical reasoning, communication, ethics,
teamwork, and safe care within the relevant specialty.

Prepare:
- History-taking, examination, differential diagnosis, and investigations
- Prioritization, escalation, handoffs, and evidence-based decisions
- Shared decision-making, consent, confidentiality, and patient education
- Reflection, teamwork, and handling uncertainty or clinical errors

Common questions:
- How would you assess a patient with an acute change in condition?
- How do you explain uncertainty or treatment options to a patient?
- What would you do if you disagreed with a colleague's plan?
- Describe a case that changed how you practice.

Tailor examples to the specialty and local protocols. Keep patient safety,
clear escalation, and respectful communication central.
""",

# 106. PHYSIOTHERAPIST
"help me in preparation for physiotherapist interview": """
A Physiotherapist interview tests assessment, evidence-based treatment,
patient education, and progress measurement.

Prepare:
- Functional assessment, goal setting, and individualized care plans
- Exercise prescription, rehabilitation progression, and outcome measures
- Red flags, contraindications, documentation, and referral pathways
- Motivational communication, adherence, and multidisciplinary teamwork

Common questions:
- How would you adapt a plan when a patient is not progressing?
- How do you set meaningful, measurable rehabilitation goals?
- What signs would make you pause treatment and escalate care?
- Describe how you supported a patient with low adherence.

Explain how you involve the patient in decisions and review evidence of
progress before changing the treatment plan.
""",

# 107. VETERINARIAN
"help me in preparation for veterinarian interview": """
A Veterinarian interview evaluates clinical reasoning, animal welfare,
communication with owners, and teamwork in a veterinary setting.

Prepare:
- History, examination, differential diagnosis, and diagnostic planning
- Triage, pain management, preventive care, and treatment monitoring
- Informed consent, welfare, confidentiality, and ethical decisions
- Communicating costs, uncertainty, and follow-up care to owners

Common questions:
- How would you triage several animals needing urgent attention?
- How do you discuss a difficult prognosis with an owner?
- What would you do if an owner declines a recommended treatment?
- Describe a case where you changed your initial assessment.

Tailor examples to the species and practice type, and balance clinical
judgment with animal welfare and compassionate client communication.
""",

# 108. RENEWABLE ENERGY ENGINEER
"help me in preparation for renewable energy engineer interview": """
A Renewable Energy Engineer interview tests technical design and the
practical delivery of clean-energy projects.

Prepare:
- Solar, wind, storage, grid connection, or the role's specific technology
- Resource assessment, energy yield, sizing, and performance modeling
- Electrical or mechanical design, safety, commissioning, and maintenance
- Permitting, environmental constraints, cost, and project trade-offs

Common questions:
- How would you estimate a site's energy production?
- What factors affect the choice of storage capacity?
- How would you investigate a system producing below forecast?
- How do grid or site constraints change a project design?

State assumptions and units clearly, and connect engineering choices to
reliability, safety, lifecycle cost, and environmental goals.
""",

# 109. CLOUD SECURITY ENGINEER
"help me in preparation for cloud security engineer interview": """
A Cloud Security Engineer interview evaluates how you protect cloud
environments through architecture, automation, and incident response.

Prepare:
- Identity and access management, least privilege, and key management
- Network segmentation, encryption, logging, and configuration controls
- Threat modeling, vulnerability management, and security automation
- Cloud incident detection, containment, recovery, and communication

Common questions:
- How would you investigate a publicly exposed storage resource?
- How do you manage secrets across cloud workloads?
- How would you reduce excessive permissions at scale?
- Which logs would help you investigate a suspicious identity?

Describe a defense-in-depth approach and explain how you validate that
controls work without disrupting legitimate service operations.
""",

# 110. OPERATIONS RESEARCH ANALYST
"help me in preparation for operations research analyst interview": """
An Operations Research Analyst interview tests mathematical modeling,
optimization, data analysis, and practical decision support.

Prepare:
- Linear and integer programming, constraints, and objective functions
- Probability, simulation, forecasting, and sensitivity analysis
- Python, R, SQL, spreadsheets, or optimization tools used by the team
- Translating operational needs into a model people can implement

Common questions:
- How would you model a staff scheduling problem?
- What would you do if an optimization model is infeasible?
- How do you test whether model assumptions are realistic?
- How would you explain a trade-off to an operations leader?

Walk through the problem formulation, assumptions, validation, and
implementation plan—not only the solver or mathematical result.
""",

# 111. PRODUCT MARKETING MANAGER
"help me in preparation for product marketing manager interview": """
A Product Marketing Manager interview focuses on positioning, customer
insight, go-to-market plans, and alignment across teams.

Prepare:
- Customer segments, use cases, competitive research, and messaging
- Positioning, launches, sales enablement, and product adoption
- Pricing or packaging research and market feedback
- Launch goals, funnel metrics, and learning after release

Common questions:
- How would you position a product in a crowded market?
- How do you turn customer research into useful messaging?
- What would you include in a go-to-market plan?
- Describe how you measured a launch and adapted afterward.

Show how you connect customer evidence to a clear value proposition
and coordinate product, sales, and marketing toward shared outcomes.
""",
}

def _normalize_interview_text(value):
    text = str(value or "").lower().strip()
    text = text.replace("-", " ").replace("/", " ")
    text = text.translate(str.maketrans("", "", string.punctuation))
    return re.sub(r"\s+", " ", text).strip()


_INTERVIEW_RESPONSE_PREFIX = "help me in preparation for "
_INTERVIEW_RESPONSE_SUFFIX = " interview"
_INTERVIEW_RESPONSE_KEYS_BY_ROLE = {
    _normalize_interview_text(
        key[len(_INTERVIEW_RESPONSE_PREFIX):-len(_INTERVIEW_RESPONSE_SUFFIX)]
    ): key
    for key in JOB_FAST_RESPONSES
    if key.startswith(_INTERVIEW_RESPONSE_PREFIX)
    and key.endswith(_INTERVIEW_RESPONSE_SUFFIX)
}


def match_job_interview_request(message):
    """Return the canonical response key and answer for a supported interview request.

    Accept common ways of asking for help preparing for a role-specific
    interview, then route them to the detailed response already defined above.
    """
    text = _normalize_interview_text(message)

    request_patterns = (
        r"(?:please )?help me (?:to )?prepare for (.+?) interview",
        r"(?:please )?help me in preparation for (.+?) interview",
        r"(?:please )?prepare me for (.+?) interview",
        r"(?:please )?prepare for (.+?) interview",
    )
    for pattern in request_patterns:
        match = re.fullmatch(pattern, text)
        if not match:
            continue

        role = _normalize_interview_text(match.group(1))
        role = re.sub(r"^(?:a|an|the|my)\s+", "", role).strip()
        canonical_key = _INTERVIEW_RESPONSE_KEYS_BY_ROLE.get(role)
        if canonical_key:
            return canonical_key, JOB_FAST_RESPONSES[canonical_key]

    return None
