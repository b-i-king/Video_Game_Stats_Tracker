import { MetadataRoute } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://vgst.app";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url:             SITE_URL,
      lastModified:    new Date(),
      changeFrequency: "weekly",
      priority:        1.0,
    },
    {
      url:             `${SITE_URL}/leaderboard`,
      lastModified:    new Date(),
      changeFrequency: "daily",
      priority:        0.9,
    },
    {
      url:             `${SITE_URL}/stats`,
      lastModified:    new Date(),
      changeFrequency: "weekly",
      priority:        0.8,
    },
    {
      url:             `${SITE_URL}/about`,
      lastModified:    new Date(),
      changeFrequency: "monthly",
      priority:        0.7,
    },
    {
      url:             `${SITE_URL}/integrations`,
      lastModified:    new Date(),
      changeFrequency: "monthly",
      priority:        0.6,
    },
    {
      url:             `${SITE_URL}/privacy`,
      lastModified:    new Date(),
      changeFrequency: "yearly",
      priority:        0.3,
    },
    {
      url:             `${SITE_URL}/terms`,
      lastModified:    new Date(),
      changeFrequency: "yearly",
      priority:        0.3,
    },
  ];
}
