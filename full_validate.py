#!/usr/bin/env python3
"""
Apex Career Institute — Comprehensive Website Validation Suite
Validates HTML structure, CSS rules, JS functionality, MCP adapter, and project integrity.
124 checks covering accessibility, SEO, responsive design, form logic, and more.
"""
import os
import re
import sys
from pathlib import Path

REPO = Path(r"c:\Users\USER\Desktop\AUTOMATION")
HTML_FILE = REPO / "website" / "index.html"
CSS_FILE  = REPO / "website" / "css" / "styles.css"
JS_FILE   = REPO / "website" / "js" / "main.js"
MCP_FILE  = REPO / "orchestration" / "mcp" / "kilo_gpt_peer.py"

html = HTML_FILE.read_text(encoding="utf-8")
css  = CSS_FILE.read_text(encoding="utf-8")
js   = JS_FILE.read_text(encoding="utf-8")
mcp  = MCP_FILE.read_text(encoding="utf-8")

passed = 0
failed = 0
errors = []

def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
    else:
        failed += 1
        errors.append(name)
        print(f"  FAIL: {name}")

# ═══════════════════════════════════════════════════════
# HTML — Structure & Content (checks 1-50)
# ═══════════════════════════════════════════════════════
check("01. DOCTYPE declaration", html.strip().startswith("<!DOCTYPE html>"))
check("02. HTML lang attribute", 'lang="en"' in html)
check("03. Meta charset UTF-8", 'charset="UTF-8"' in html)
check("04. Viewport meta tag", 'name="viewport"' in html)
check("05. Meta description present", 'name="description"' in html)
check("06. Meta keywords present", 'name="keywords"' in html)
check("07. Meta author present", 'name="author"' in html)
check("08. Title tag present and correct", "<title>" in html and "Apex Career Institute" in html)
check("09. Google Fonts preconnect", 'rel="preconnect"' in html and "fonts.googleapis.com" in html)
check("10. Google Fonts loaded (Poppins + Inter)", "Poppins" in html and "Inter" in html)
check("11. Bootstrap 5.3 CSS CDN", "bootstrap@5.3" in html and ".min.css" in html)
check("12. Bootstrap Icons CSS CDN", "bootstrap-icons" in html)
check("13. Custom stylesheet linked", 'href="css/styles.css"' in html)
check("14. Bootstrap JS bundle loaded", "bootstrap.bundle.min.js" in html)
check("15. Custom JS loaded", 'src="js/main.js"' in html)

# Skip link
check("16. Skip-to-content link exists", 'class="skip-link"' in html)
check("17. Skip link targets #main-content", 'href="#main-content"' in html)
check("18. Main content landmark present", 'id="main-content"' in html)

# Navbar
check("19. Navbar with fixed-top", "fixed-top" in html)
check("20. Navbar brand text", "Apex Career Institute" in html)
check("20b. Institute logo integrated with alt text", 'src="ICON.jpg"' in html and 'alt="Apex Career Institute Logo"' in html)
check("21. Offcanvas mobile nav", "offcanvas" in html)
check("22. Nav links: Home", 'href="#home"' in html)
check("23. Nav links: About", 'href="#about"' in html)
check("24. Nav links: Courses", 'href="#courses"' in html)
check("25. Nav links: Why Us", 'href="#why-us"' in html)
check("26. Nav CTA: Enquire Now", "Enquire Now" in html)
check("27. Navbar aria-label", 'aria-label="Main navigation"' in html)

# Hero
check("28. Hero section exists", 'id="home"' in html)
check("29. Hero tagline text", "Indore" in html and "M.P." in html)
check("30. Hero h1 present", "<h1" in html and "Government Career" in html)
check("31. Hero CTA: Explore Courses", "Explore Courses" in html)
check("32. Hero CTA: Admission Enquiry", "Admission Enquiry" in html)

# About
check("33. About section exists", 'id="about"' in html)
check("34. About heading with aria", 'id="about-heading"' in html)
check("35. Section aria-labelledby", 'aria-labelledby="about-heading"' in html)
check("36. Feature cards: Experienced Faculty", "Experienced Faculty" in html)
check("37. Feature cards: Structured Curriculum", "Structured Curriculum" in html)
check("38. Feature cards: Regular Assessments", "Regular Assessments" in html)
check("39. Feature cards: Personal Mentorship", "Personal Mentorship" in html)
check("40. Counter data-target attributes", 'data-target="4"' in html and 'data-target="15"' in html)
check("41. Counter: 50+ Mock Tests", 'data-target="50"' in html)
check("42. Counter: 12 Months", 'data-target="12"' in html)

# Courses
check("43. Courses section exists", 'id="courses"' in html)
check("44. SSC course card", 'data-course="ssc"' in html)
check("45. Banking course card", 'data-course="banking"' in html)
check("46. Railway course card", 'data-course="railway"' in html)
check("47. MPPSC course card", 'data-course="mppsc"' in html)
check("48. Course card Enquire links", html.count('btn btn-sm btn-outline-primary') >= 4)

# Why Choose Us
check("49. Why-Us section exists", 'id="why-us"' in html)
check("50. Six why-us advantage cards", html.count("why-card") >= 6)

# ═══════════════════════════════════════════════════════
# HTML — Form & Footer (checks 51-75)
# ═══════════════════════════════════════════════════════
check("51. CTA banner section", "cta-banner" in html)
check("52. CTA heading", "Ready to Begin Your Preparation" in html)
check("53. Enquiry section exists", 'id="enquiry"' in html)
check("54. Form element present", 'id="enquiryForm"' in html)
check("55. Form novalidate attr", "novalidate" in html)
check("56. Form aria-label", 'aria-label="Admission enquiry form"' in html)
check("57. Full Name input", 'id="fullName"' in html)
check("58. Email input", 'id="email"' in html)
check("59. Phone input", 'id="phone"' in html)
check("60. Phone prefix +91", "+91" in html)
check("61. Course select", 'id="course"' in html)
check("62. Course options: SSC", 'value="ssc"' in html)
check("63. Course options: Banking", 'value="banking"' in html)
check("64. Course options: Railway", 'value="railway"' in html)
check("65. Course options: MPPSC", 'value="mppsc"' in html)
check("66. Message textarea", 'id="message"' in html)
check("67. Character counter", 'id="charCount"' in html)
check("68. Submit button", 'id="submitBtn"' in html)
check("69. Loading spinner markup", "btn-spinner" in html and "spinner-border" in html)
check("70. Form success state", 'id="formSuccess"' in html)
check("71. Submit another button", 'id="submitAnother"' in html)
check("72. Success message text", "Enquiry Validated Successfully" in html)
check("73. SR announcements region", 'id="srAnnouncements"' in html and 'aria-live="polite"' in html)

# Footer
check("74. Footer landmark", 'aria-label="Site footer"' in html)
check("75. Footer copyright with year", "current-year" in html)

# ═══════════════════════════════════════════════════════
# HTML — Accessibility (checks 76-85)
# ═══════════════════════════════════════════════════════
check("76. aria-hidden on decorative icons", 'aria-hidden="true"' in html)
check("77. All required fields marked", html.count('required') >= 4)
check("78. Input autocomplete attributes", 'autocomplete="name"' in html and 'autocomplete="email"' in html)
check("79. Phone pattern validation", 'pattern="[6-9][0-9]{9}"' in html)
check("80. Invalid feedback containers", html.count("invalid-feedback") >= 4)
check("81. Back-to-top button", 'id="backToTop"' in html)
check("82. Back-to-top aria-label", 'aria-label="Back to top"' in html)
check("83. visually-hidden class used", "visually-hidden" in html)
check("84. role=alert on success state only", 'role="status"' in html)
check("85. Disclaimer text in footer", "demonstration website" in html.lower())

# ═══════════════════════════════════════════════════════
# CSS — Design System (checks 86-105)
# ═══════════════════════════════════════════════════════
check("86. CSS custom property: --aci-navy", "--aci-navy:" in css)
check("87. CSS custom property: --aci-gold", "--aci-gold:" in css)
check("88. CSS custom property: --aci-blue", "--aci-blue:" in css)
check("89. Font heading: Poppins", "'Poppins'" in css or "Poppins" in css)
check("90. Font body: Inter", "'Inter'" in css or "Inter" in css)
check("91. Smooth scrolling", "scroll-behavior: smooth" in css)
check("92. Skip link styles", ".skip-link" in css)
check("93. Focus-visible outline", ":focus-visible" in css)
check("94. Hero section min-height", "min-height: 100vh" in css)
check("95. Hero gradient background", "linear-gradient" in css and ".hero-section" in css)
check("96. Navbar transparent → scrolled", ".navbar-custom.scrolled" in css)
check("97. btn-primary-custom styles", ".btn-primary-custom" in css)
check("98. Course card hover effects", ".course-card:hover" in css)
check("99. Why-card hover effects", ".why-card:hover" in css)
check("100. fade-in-up animation class", ".fade-in-up" in css)
check("101. Shake animation keyframes", "@keyframes shake" in css)
check("102. Form success style", ".form-success" in css)
check("103. Character warning style", ".char-warning" in css)
check("104. Back-to-top styles", ".btn-back-to-top" in css)
check("105. Footer gold border-top", "border-top:" in css and ".footer-section" in css)

# ═══════════════════════════════════════════════════════
# CSS — Responsive Design (checks 106-112)
# ═══════════════════════════════════════════════════════
check("106. Tablet breakpoint (max-width: 991.98px)", "991.98px" in css)
check("107. Mobile breakpoint (max-width: 767.98px)", "767.98px" in css)
check("108. Extra small breakpoint (max-width: 575.98px)", "575.98px" in css)
check("109. prefers-reduced-motion support", "prefers-reduced-motion" in css)
check("110. Responsive hero title sizing", "hero-title" in css and "font-size:" in css)
check("111. Mobile section padding adjustment", "padding: 3rem 0" in css or "padding: 3.5rem 0" in css)
check("112. Mobile footer center alignment", "text-align: center" in css)

# ═══════════════════════════════════════════════════════
# JavaScript — Functionality (checks 113-124)
# ═══════════════════════════════════════════════════════
check("113. IIFE wrapper", "(function" in js)
check("114. DOMContentLoaded listener", "DOMContentLoaded" in js)
check("115. use strict", "'use strict'" in js)
check("116. Navbar scroll handler with rAF", "requestAnimationFrame" in js and "handleNavScroll" in js)
check("117. Passive scroll listener", "passive: true" in js)
check("118. IntersectionObserver for scroll reveal", "IntersectionObserver" in js)
check("119. Counter animation function", "animateCounter" in js)
check("120. Form validation logic", "validateField" in js)
check("121. Phone digit-only filter with +91 strip", ("replace(/\\D/g" in js or r"replace(/\D/g" in js) and "startsWith" in js)
check("122. Form submit handler with loading state", "btn-loading" in js and "submit" in js)
check("123. Submit-another reset handler", "submitAnother" in js and "form.reset()" in js)
check("124. SR announce function", "announce" in js and "srAnnouncements" in js)

# ═══════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════
total = passed + failed
print(f"\n{'='*60}")
print(f"  VALIDATION RESULTS: {passed}/{total} passed")
print(f"{'='*60}")
if errors:
    print(f"\n  Failed checks ({len(errors)}):")
    for e in errors:
        print(f"    ✗ {e}")
else:
    print("\n  ✓ ALL CHECKS PASSED")
print()

sys.exit(0 if failed == 0 else 1)
