from typing import Any, Dict, List


class RequestAnalyzer:

    def analyze(
        self,
        user_message: str,
        uploaded_files: List[Any] | None = None,
        images: List[Any] | None = None,
        video_frames: List[Any] | None = None,
    ) -> Dict[str, Any]:

        text = (user_message or "").strip().lower()

        uploaded_files = uploaded_files or []
        images = images or []
        video_frames = video_frames or []

        result = {
            "intent": "general_chat",
            "domain": "general",
            "actions": [],
            "complexity": "low",

            "requires_web": False,
            "requires_file": bool(uploaded_files),
            "requires_image": bool(images),
            "requires_video": bool(video_frames),

            "requires_platform_action": False,
            "required_capabilities": [],
        }

        # -----------------------------------------
        # JOBS
        # -----------------------------------------

        if any(word in text for word in (
            "job",
            "jobs",
            "vacancy",
            "vacancies",
            "hiring",
            "career",
            "careers",
            "employment",
        )):

            result["domain"] = "jobs"

            if any(word in text for word in (
                "find",
                "search",
                "look for",
                "show me",
                "available",
                "openings",
            )):
                result["intent"] = "job_search"
                result["actions"].append("search")
                result["requires_web"] = True
                result["requires_platform_action"] = True
                result["required_capabilities"].append(
                    "jobs.search"
                )

            if any(word in text for word in (
                "apply",
                "application",
                "submit",
            )):
                result["intent"] = "job_application"
                result["actions"].append("apply")
                result["requires_platform_action"] = True
                result["required_capabilities"].append(
                    "jobs.apply"
                )

            if any(word in text for word in (
                "save",
                "bookmark",
                "saved jobs",
            )):
                result["actions"].append("save")
                result["requires_platform_action"] = True
                result["required_capabilities"].append(
                    "jobs.save"
                )

        # -----------------------------------------
        # RESUME
        # -----------------------------------------

        if any(word in text for word in (
            "resume",
            "cv",
        )):

            result["domain"] = "resume"

            if any(word in text for word in (
                "analyze",
                "analyse",
                "review",
                "check",
            )):
                result["intent"] = "resume_analysis"
                result["actions"].append("analyze")

            elif any(word in text for word in (
                "create",
                "make",
                "build",
                "generate",
            )):
                result["intent"] = "resume_create"
                result["actions"].append("create")
                result["requires_platform_action"] = True
                result["required_capabilities"].append(
                    "resume.create"
                )

            elif any(word in text for word in (
                "edit",
                "improve",
                "modify",
                "rewrite",
            )):
                result["intent"] = "resume_edit"
                result["actions"].append("edit")
                result["requires_platform_action"] = True
                result["required_capabilities"].append(
                    "resume.edit"
                )

        # -----------------------------------------
        # APPLICATIONS
        # -----------------------------------------

        if any(word in text for word in (
            "application",
            "applications",
            "applied",
        )):

            result["domain"] = "applications"

            if any(word in text for word in (
                "track",
                "status",
                "where is",
                "update",
            )):
                result["intent"] = "application_tracking"
                result["actions"].append("track")
                result["requires_platform_action"] = True
                result["required_capabilities"].append(
                    "applications.track"
                )

        # -----------------------------------------
        # FILES
        # -----------------------------------------

        if uploaded_files:

            result["requires_file"] = True

            if result["intent"] == "general_chat":
                result["intent"] = "file_analysis"
                result["domain"] = "files"
                result["actions"].append("analyze")

        # -----------------------------------------
        # IMAGE
        # -----------------------------------------

        if images:

            result["requires_image"] = True

            if result["intent"] == "general_chat":
                result["intent"] = "image_analysis"
                result["domain"] = "vision"
                result["actions"].append("analyze")

        # -----------------------------------------
        # VIDEO
        # -----------------------------------------

        if video_frames:

            result["requires_video"] = True

            if result["intent"] == "general_chat":
                result["intent"] = "video_analysis"
                result["domain"] = "video"
                result["actions"].append("analyze")

        # -----------------------------------------
        # CODING / PROGRAMMING
        # -----------------------------------------

        if any(word in text for word in (
            "python",
            "javascript",
            "java",
            "c++",
            "c programming",
            "programming",
            "program",
            "code",
            "coding",
            "debug",
            "debugging",
            "algorithm",
            "function",
            "class",
            "api",
            "sql",
            "html",
            "css",
        )):

            result["intent"] = "coding"
            result["domain"] = "coding"

            if any(word in text for word in (
                "write",
                "create",
                "build",
            )):
                result["actions"].append("create")

            elif any(word in text for word in (
                "debug",
                "fix",
            )):
                result["actions"].append("debug")

            else:
                result["actions"].append("solve")

        # -----------------------------------------
        # EDUCATION
        # -----------------------------------------

        if any(word in text for word in (
            "explain",
            "teach me",
            "what is",
            "how does",
            "how do",
            "why does",
            "why is",
            "solve",
            "calculate",
        )):

            if result["intent"] == "general_chat":
                result["intent"] = "educational"
                result["domain"] = "education"
                result["actions"].append("explain")

        # -----------------------------------------
        # WEB / CURRENT INFORMATION
        # -----------------------------------------

        if any(word in text for word in (
            "latest",
            "current",
            "today",
            "recent",
            "news",
            "price",
            "weather",
            "live",
            "right now",
        )):
            result["requires_web"] = True

        # -----------------------------------------
        # COMPLEXITY
        # -----------------------------------------

        complexity_indicators = 0

        if any(word in text for word in (
            "complex",
            "advanced",
            "deep",
            "deeply",
            "detailed",
            "step by step",
            "thoroughly",
            "in depth",
            "comprehensive",
            "architecture",
            "design",
            "compare",
            "evaluate",
            "analyze",
            "analyse",
        )):
            complexity_indicators += 2

        if any(word in text for word in (
            "reasoning",
            "reason",
            "tradeoff",
            "trade-off",
            "pros and cons",
            "multiple approaches",
        )):
            complexity_indicators += 2

        word_count = len(text.split())

        if word_count > 80:
            complexity_indicators += 2

        elif word_count > 40:
            complexity_indicators += 1

        if len(result["actions"]) >= 3:
            complexity_indicators += 2

        elif len(result["actions"]) >= 2:
            complexity_indicators += 1

        if result["requires_file"] or result["requires_video"]:
            complexity_indicators += 2

        elif result["requires_image"]:
            complexity_indicators += 1

        if complexity_indicators >= 4:
            result["complexity"] = "high"

        elif complexity_indicators >= 2:
            result["complexity"] = "medium"

        else:
            result["complexity"] = "low"

        # -----------------------------------------
        # CLEANUP
        # -----------------------------------------

        result["actions"] = list(
            dict.fromkeys(result["actions"])
        )

        result["required_capabilities"] = list(
            dict.fromkeys(
                result["required_capabilities"]
            )
        )

        return result


def analyze_request(
    user_message: str,
    uploaded_files=None,
    images=None,
    video_frames=None,
) -> Dict[str, Any]:

    analyzer = RequestAnalyzer()

    return analyzer.analyze(
        user_message=user_message,
        uploaded_files=uploaded_files,
        images=images,
        video_frames=video_frames,
    )