import json
import os
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app import create_app, seo_site_url
from config import Config
from extensions import db
from models import News, Product


class SearchEngineOptimizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = os.path.join(self.temp_dir.name, "seo.sqlite3")
        upload_folder = os.path.join(self.temp_dir.name, "uploads")

        class TestConfig(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path}"
            UPLOAD_FOLDER = upload_folder
            SITE_URL = "https://www.deecoder.test"

        self.app = create_app(TestConfig)
        with self.app.app_context():
            db.create_all()
            db.session.add_all(
                [
                    News(
                        title="Published story",
                        slug="published-story",
                        summary="A published news summary.",
                        content="Published content.",
                        published=True,
                    ),
                    News(
                        title="Draft story",
                        slug="draft-story",
                        summary="A private draft summary.",
                        content="Draft content.",
                        published=False,
                    ),
                    Product(
                        name="Published product",
                        slug="published-product",
                        description="A published product description.",
                        published=True,
                    ),
                    Product(
                        name="Draft product",
                        slug="draft-product",
                        description="A private draft product.",
                        published=False,
                    ),
                ]
            )
            db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def test_site_url_requires_a_configured_https_origin(self):
        for site_url in (
            "",
            "http://www.deecoder.com",
            "http://127.0.0.1:5000",
            "https://YOUR_USERNAME.pythonanywhere.com",
            "https://example.com",
            "https://www.deecoder.com/path",
            "https://[invalid",
        ):
            with self.subTest(site_url=site_url):
                self.assertIsNone(seo_site_url(site_url))

        self.assertEqual(seo_site_url("https://www.deecoder.com/"), "https://www.deecoder.com")

    def test_homepage_and_company_pages_have_canonical_metadata(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.data, "html.parser")
        self.assertEqual(soup.title.string, "DeeCoder Technologies | Official Website")
        self.assertIn("DeeCoder Technologies", soup.h1.get_text())
        self.assertEqual(
            soup.find("link", rel="canonical")["href"],
            "https://www.deecoder.test/",
        )
        self.assertEqual(
            soup.find("meta", property="og:url")["content"],
            "https://www.deecoder.test/",
        )
        for attribute in ("og:type", "og:title", "og:description", "og:url", "og:image"):
            with self.subTest(attribute=attribute):
                self.assertEqual(len(soup.find_all("meta", property=attribute)), 1)

        scripts = soup.find_all("script", type="application/ld+json")
        self.assertEqual(len(scripts), 1)
        schema = json.loads(scripts[0].string)
        self.assertEqual(schema["@type"], "Organization")
        self.assertEqual(schema["name"], "DeeCoder Technologies")
        self.assertEqual(schema["url"], "https://www.deecoder.test")
        self.assertEqual(
            schema["contactPoint"]["email"],
            "deecodertechnologiesworldwide@gmail.com",
        )
        self.assertEqual(schema["contactPoint"]["telephone"], "+2348075346224")
        self.assertNotIn("sameAs", schema)
        self.assertNotIn("address", schema)

        for path, expected_heading in (
            ("/about", "About DeeCoder Technologies"),
            ("/contact", "Contact DeeCoder Technologies"),
        ):
            with self.subTest(path=path):
                page = self.client.get(path)
                self.assertEqual(page.status_code, 200)
                page_soup = BeautifulSoup(page.data, "html.parser")
                self.assertEqual(page_soup.h1.get_text(strip=True), expected_heading)
                self.assertEqual(len(page_soup.find_all("link", rel="canonical")), 1)
                if path == "/about":
                    self.assertEqual(
                        len(page_soup.find_all("script", type="application/ld+json")),
                        1,
                    )

    def test_robots_txt_excludes_nonpublic_paths(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        content = response.get_data(as_text=True)
        self.assertIn("Allow: /", content)
        self.assertIn("Disallow: /admin/", content)
        self.assertIn("Disallow: /api/", content)
        self.assertIn("Disallow: /unsubscribe/", content)
        self.assertIn("Disallow: /uploads/", content)
        self.assertIn("Sitemap: https://www.deecoder.test/sitemap.xml", content)

    def test_official_site_url_publishes_expected_absolute_sitemap_urls(self):
        official_origin = "https://deecodertechnologies.pythonanywhere.com"
        self.app.config["SITE_URL"] = official_origin

        sitemap_response = self.client.get("/sitemap.xml")
        self.assertEqual(sitemap_response.status_code, 200)
        self.assertIn("application/xml", sitemap_response.content_type)
        root = ET.fromstring(sitemap_response.data)
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = [
            entry.text
            for entry in root.findall("s:url/s:loc", namespace)
        ]

        for path in (
            "/",
            "/about",
            "/contact",
            "/news",
            "/projects",
            "/products",
            "/videos",
            "/terms",
            "/privacy",
            "/news/published-story",
            "/products/published-product",
        ):
            with self.subTest(path=path):
                self.assertIn(f"{official_origin}{path}", locations)
        self.assertEqual(len(locations), len(set(locations)))
        self.assertTrue(all(location.startswith(official_origin) for location in locations))
        self.assertFalse(any(urlsplit(location).query or urlsplit(location).fragment for location in locations))
        self.assertFalse(any("localhost" in location or "127.0.0.1" in location for location in locations))
        self.assertFalse(any("/admin" in location or "/api/" in location for location in locations))

        robots_response = self.client.get("/robots.txt")
        self.assertEqual(robots_response.status_code, 200)
        self.assertIn(
            f"Sitemap: {official_origin}/sitemap.xml",
            robots_response.get_data(as_text=True),
        )

    def test_sitemap_uses_canonical_urls_and_only_published_content(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        root = ET.fromstring(response.data)
        namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = {
            entry.text
            for entry in root.findall("s:url/s:loc", namespace)
        }
        self.assertIn("https://www.deecoder.test/", locations)
        self.assertIn("https://www.deecoder.test/about", locations)
        self.assertIn("https://www.deecoder.test/contact", locations)
        self.assertIn("https://www.deecoder.test/news/published-story", locations)
        self.assertIn("https://www.deecoder.test/products/published-product", locations)
        self.assertNotIn("https://www.deecoder.test/news/draft-story", locations)
        self.assertNotIn("https://www.deecoder.test/products/draft-product", locations)
        self.assertFalse(any("/admin/" in location or "/api/" in location for location in locations))
        for location in locations:
            with self.subTest(location=location):
                self.assertEqual(self.client.get(urlsplit(location).path).status_code, 200)

    def test_public_page_titles_descriptions_and_canonicals_are_unique(self):
        paths = (
            "/",
            "/about",
            "/contact",
            "/news",
            "/projects",
            "/products",
            "/videos",
            "/terms",
            "/privacy",
        )
        titles = set()
        descriptions = set()
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                soup = BeautifulSoup(response.data, "html.parser")
                title = soup.title.get_text(strip=True)
                description = soup.find("meta", attrs={"name": "description"})["content"]
                canonical = soup.find("link", rel="canonical")["href"]
                self.assertNotIn(title, titles)
                self.assertNotIn(description, descriptions)
                self.assertEqual(canonical, f"https://www.deecoder.test{path}" if path != "/" else "https://www.deecoder.test/")
                titles.add(title)
                descriptions.add(description)

    def test_about_page_contains_complete_supplied_content_and_working_contact_links(self):
        about_response = self.client.get("/about")
        self.assertEqual(about_response.status_code, 200)
        about = BeautifulSoup(about_response.data, "html.parser")
        self.assertEqual(
            [heading.get_text(" ", strip=True) for heading in about.select("main h2")],
            [
                "Practical Digital Solutions for Businesses, Schools, and Individuals",
                "Who We Are",
                "Our Services",
                "Our Mission",
                "Our Vision",
                "Our Values",
                "DeeCoder Academy",
                "Our Commitment to Customers",
                "Let's Work Together",
            ],
        )
        expected_paragraphs = [
            "Welcome to DeeCoder Technologies, a digital technology business focused on website development, software solutions, educational platforms, and e-commerce systems.",
            "We help businesses, schools, entrepreneurs, and individuals establish and improve their digital presence through practical technology solutions designed around their needs.",
            "Our goal is to make technology useful, accessible, and effective by creating digital products that help our clients present their services, connect with their audiences, and manage their activities online.",
            "DeeCoder Technologies was established around a simple idea: technology should help people solve real problems and create new opportunities.",
            "We focus on understanding the needs of our clients and developing digital solutions that align with their objectives. Whether a client needs a business website, a student portal, a school website, or an online shopping platform, we aim to provide a solution that is functional, professional, and easy to use.",
            "We believe that successful technology projects require more than writing code. They also require clear communication, thoughtful design, attention to detail, and an understanding of the people who will use the final product.",
            "We develop websites for businesses, schools, organizations, professionals, and individuals who want to establish or strengthen their online presence.",
            "We provide digital solutions designed for educational environments, including student portals and school websites that support the presentation of school information and relevant online services.",
            "We build online shopping platforms that allow businesses to display products, present information, and serve customers through digital channels.",
            "We work on digital products and software solutions intended to address specific needs. We also offer selected ready-made digital solutions for customers looking for practical starting points for their projects.",
            "We assist with website updates, functionality improvements, troubleshooting, and other technical requirements, depending on the project and agreed scope of work.",
            "Our mission is to deliver practical digital solutions that help businesses, educational institutions, entrepreneurs, and individuals use technology to work more effectively and grow their online presence.",
            "Our vision is to build a respected digital technology brand known for useful solutions, professional service, continuous learning, and responsible business practices.",
            "Quality: We aim to deliver solutions that meet agreed requirements and serve their intended purpose.",
            "Transparency: We value clear communication about project scope, pricing, timelines, and service expectations.",
            "Customer Focus: We seek to understand each customer's needs before recommending or developing a solution.",
            "Innovation: We continue exploring technologies and approaches that can improve the usefulness of our products and services.",
            "Responsibility: We recognize the importance of protecting customer information, communicating honestly, and handling business engagements professionally.",
            "DeeCoder Academy operates under DeeCoder Technologies as part of our interest in technology education and digital skills development. It supports our broader goal of helping people learn, develop practical knowledge, and engage with opportunities in the digital world.",
            "At DeeCoder Technologies, we understand that choosing a technology provider requires confidence and clear information.",
            "We aim to provide customers with understandable service descriptions, transparent project expectations, appropriate communication, and solutions aligned with the requirements agreed upon.",
            "Before starting a project or purchasing a digital product, customers are encouraged to confirm the features included, pricing, delivery arrangements, support terms, and applicable conditions.",
            "We also encourage customers to communicate with us through the official contact details published on this website to help ensure they are dealing with the correct business.",
            "Whether you are planning a new business website, need a student portal, want to launch an online store, or have another digital project in mind, DeeCoder Technologies welcomes your inquiry.",
            "Tell us about your goals, and we can discuss your requirements and the available options.",
            "Contact us through our official Contact page or WhatsApp channel to get started.",
        ]
        actual_paragraphs = [
            re.sub(r"\s+", " ", paragraph.get_text("", strip=False)).strip()
            for paragraph in about.select("main p")
        ]
        for paragraph in expected_paragraphs:
            with self.subTest(paragraph=paragraph):
                self.assertIn(paragraph, actual_paragraphs)
        self.assertIn(
            "DeeCoder Technologies — Innovative Solutions. Digital Growth. Your Success.",
            [text.get_text(" ", strip=True) for text in about.select("main strong")],
        )

        homepage_response = self.client.get("/")
        self.assertEqual(homepage_response.status_code, 200)
        homepage = BeautifulSoup(homepage_response.data, "html.parser")
        mission = about.find(id="about-mission").find_next("p").get_text(strip=True)
        vision = about.find(id="about-vision").find_next("p").get_text(strip=True)
        self.assertEqual(
            homepage.select("#mission .mv-card")[0].find_all("p")[-1].get_text(strip=True),
            mission,
        )
        self.assertEqual(
            homepage.select("#mission .mv-card")[1].find_all("p")[-1].get_text(strip=True),
            vision,
        )

        work_together_section = about.find(id="about-work-together").find_parent("section")
        contact_links = work_together_section.select('a[href="/contact"]')
        self.assertEqual(len(contact_links), 1)
        self.assertEqual(self.client.get(contact_links[0]["href"]).status_code, 200)
        whatsapp_links = about.select('a[href="https://wa.me/2348075346224"]')
        self.assertEqual(len(whatsapp_links), 1)

    def test_detail_page_metadata_is_not_duplicated(self):
        response = self.client.get("/news/published-story")
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.data, "html.parser")
        for attribute in ("og:type", "og:title", "og:description", "og:url", "og:image"):
            with self.subTest(attribute=attribute):
                self.assertEqual(len(soup.find_all("meta", property=attribute)), 1)
        self.assertEqual(len(soup.find_all("link", rel="canonical")), 1)

    def test_sitemap_is_not_published_without_a_real_https_site_url(self):
        self.app.config["SITE_URL"] = "http://127.0.0.1:5000"
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"Configure SITE_URL", response.data)
        self.assertNotIn(b"Sitemap:", self.client.get("/robots.txt").data)
        homepage = BeautifulSoup(self.client.get("/").data, "html.parser")
        self.assertEqual(homepage.find_all("link", rel="canonical"), [])
        self.assertEqual(homepage.find_all("meta", property="og:url"), [])
        self.assertEqual(homepage.find_all("script", type="application/ld+json"), [])


if __name__ == "__main__":
    unittest.main()
