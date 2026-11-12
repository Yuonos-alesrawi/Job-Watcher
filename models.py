from dataclasses import dataclass


@dataclass
class Job:
    source: str          # greenhouse | lever | ashby
    company: str         # board token / slug
    job_id: str
    title: str
    location: str
    remote: "bool | None"  # None = the source does not say
    url: str
    text: str            # plain-text description
