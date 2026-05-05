"""All research queries organised by area.

Each query specifies which engine(s) to use:
  - "perplexity": real-time web search with citations (best for current data)
  - "gemini": deep analysis and synthesis (best for large-context reasoning)
  - "both": run on both engines and merge results

Perplexity excels at: current events, live URLs, real-time pricing, news, deadlines.
Gemini excels at: analysis, summarisation, pattern recognition, large-doc reasoning.
"""

COURSES_QUERIES = [
    {
        "query": (
            "List newly announced UK university courses starting in 2026-2027 "
            "in computer science, data science, AI, cybersecurity, and digital "
            "marketing. Include provider, title, UCAS code if available, tuition "
            "fees (UK and international), location, and URL. Focus on courses "
            "not yet listed on UCAS or DiscoverUni."
        ),
        "topic": "new-uk-courses-2026",
        "region": "UK",
        "engine": "perplexity",
        "area": "courses",
    },
    {
        "query": (
            "List new Swiss university and Fachhochschule programmes starting "
            "2026-2027 in technology, business, and digital fields. Include "
            "English-taught programmes. Give: institution, programme name, "
            "degree level, language, fees in CHF, URL."
        ),
        "topic": "new-swiss-courses-2026",
        "region": "Switzerland",
        "engine": "perplexity",
        "area": "courses",
    },
    {
        "query": (
            "What are the top 20 highest-demand university course subjects in "
            "the UK right now based on UCAS application data, employer demand, "
            "and graduate salary premiums? Rank them and cite sources."
        ),
        "topic": "high-demand-subjects-uk",
        "region": "UK",
        "engine": "both",
        "area": "courses",
    },
    {
        "query": (
            "List online and distance-learning degree programmes launched by "
            "Russell Group universities in the last 6 months. Include fees, "
            "duration, and how they compare to on-campus equivalents."
        ),
        "topic": "online-russell-group",
        "region": "UK",
        "engine": "perplexity",
        "area": "courses",
    },
]

JOBS_QUERIES = [
    {
        "query": (
            "List current EdTech and higher-education technology job openings "
            "in the UK, Switzerland, and remote-EU. Focus on product management, "
            "engineering, data, and sales roles at companies like Tribal, Ellucian, "
            "Anthology, Canvas, Turnitin, Jisc, and EdTech startups. "
            "For each: title, company, location, salary if stated, URL."
        ),
        "topic": "edtech-jobs-current",
        "region": "UK/CH/EU",
        "engine": "perplexity",
        "area": "jobs",
    },
    {
        "query": (
            "What are the most in-demand tech skills for higher education "
            "sector jobs in 2026? Include both technical (Python, cloud, AI/ML) "
            "and domain skills (student records, HESA, QAA). Cite job board data."
        ),
        "topic": "he-tech-skills-demand",
        "region": "UK",
        "engine": "both",
        "area": "jobs",
    },
]

FUNDING_QUERIES = [
    {
        "query": (
            "List all currently open angel investment networks, seed funds, "
            "and pre-seed programmes actively investing in European EdTech "
            "in 2026. Include: fund name, ticket size, focus, application URL, "
            "and any stated deadlines."
        ),
        "topic": "angel-seed-edtech-eu",
        "region": "EU/UK/CH",
        "engine": "perplexity",
        "area": "funding",
    },
    {
        "query": (
            "What non-dilutive funding (grants, competitions, innovation "
            "vouchers) is available right now for a Swiss-registered EdTech "
            "startup with UK university clients? Include cantonal, federal, "
            "and EU sources. Deadlines, amounts, URLs."
        ),
        "topic": "non-dilutive-swiss-edtech",
        "region": "Switzerland",
        "engine": "perplexity",
        "area": "funding",
    },
]

FILM_QUERIES = [
    {
        "query": (
            "List currently open UK and international screenwriting competitions, "
            "script calls, and writer development programmes with deadlines in "
            "the next 3 months. Include: name, organiser, deadline, entry fee, "
            "genre requirements, prize, URL."
        ),
        "topic": "screenwriting-comps-open",
        "region": "UK/International",
        "engine": "perplexity",
        "area": "film",
    },
    {
        "query": (
            "What film and TV production funding, tax relief changes, or new "
            "commissioning rounds have been announced in the UK in the last "
            "30 days? Include BFI, BBC, Channel 4, Film4, and regional funds."
        ),
        "topic": "uk-film-funding-news",
        "region": "UK",
        "engine": "perplexity",
        "area": "film",
    },
]

JOB_TRENDS_QUERIES = [
    {
        "query": (
            "What are the fastest-growing and fastest-declining occupations in "
            "the UK in 2026 according to ONS, HMRC RTI data, and LinkedIn "
            "Workforce Report? Give growth rates, median salaries, and the "
            "key skills driving demand. Focus on tech, education, and creative."
        ),
        "topic": "uk-occupation-trends-2026",
        "region": "UK",
        "engine": "both",
        "area": "job_trends",
    },
    {
        "query": (
            "Which university subjects in the UK have the highest and lowest "
            "graduate employment rates and salary premiums 5 years after "
            "graduation? Use LEO data, Graduate Outcomes, and HESA. "
            "Rank the top 20 and bottom 10."
        ),
        "topic": "graduate-outcomes-ranking",
        "region": "UK",
        "engine": "gemini",
        "area": "job_trends",
    },
    {
        "query": (
            "What are the emerging AI and automation-resistant career paths "
            "that universities should be developing courses for? Cite WEF "
            "Future of Jobs 2025, McKinsey, and Burning Glass/Lightcast data."
        ),
        "topic": "automation-resistant-careers",
        "region": "Global",
        "engine": "gemini",
        "area": "job_trends",
    },
]

FINANCIAL_QUERIES = [
    {
        "query": (
            "What are the latest student enrolment trends in UK higher education? "
            "Domestic vs international, by subject area, by university type. "
            "Impact on university finances and course viability. "
            "Cite UCAS end-of-cycle data and HESA statistics."
        ),
        "topic": "uk-enrolment-trends",
        "region": "UK",
        "engine": "both",
        "area": "financial",
    },
    {
        "query": (
            "What university IT procurement contracts have been awarded in the "
            "UK in the last 3 months? Include student records, LMS, admissions "
            "platforms, and cloud infrastructure deals. Sources: TED, Contracts "
            "Finder, FTS, university press releases."
        ),
        "topic": "uk-uni-it-procurement",
        "region": "UK",
        "engine": "perplexity",
        "area": "financial",
    },
    {
        "query": (
            "Analyse the competitive landscape for higher education management "
            "software globally. Market share estimates, recent M&A, product "
            "launches, and pricing changes for Tribal, Ellucian, Unit4, "
            "TechnologyOne, Anthology, Oracle Student Cloud, Workday Student."
        ),
        "topic": "he-software-competitive",
        "region": "Global",
        "engine": "gemini",
        "area": "financial",
    },
]

ALL_QUERIES = (
    COURSES_QUERIES
    + JOBS_QUERIES
    + FUNDING_QUERIES
    + FILM_QUERIES
    + JOB_TRENDS_QUERIES
    + FINANCIAL_QUERIES
)
