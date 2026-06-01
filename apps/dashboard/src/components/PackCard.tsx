import React, { useState, useMemo } from "react";

interface PackCategory {
  id: string;
  label: string;
  difficulty: string[];
  count: number;
}

interface PackSkill {
  name: string;
  version?: string;
  description: string;
}

interface PackData {
  name: string;
  version: string;
  description: string;
  tags: string[];
  categories: PackCategory[];
  skills: PackSkill[];
  total_prompts: number;
  author?: string;
  license?: string;
}

interface PackCardProps {
  packs: PackData[];
}

const ALL_TAGS = [
  "all",
  "backend",
  "nestjs",
  "agentic",
  "tool-use",
  "typescript",
  "frontend",
  "react",
  "nextjs",
  "debugging",
  "race-condition",
];
const DIFFICULTIES = ["all", "easy", "medium", "hard"];

export default function PackCard({ packs }: PackCardProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeTag, setActiveTag] = useState("all");
  const [activeDifficulty, setActiveDifficulty] = useState("all");

  const filtered = useMemo(() => {
    return packs.filter((pack) => {
      const tagMatch = activeTag === "all" || pack.tags.includes(activeTag);
      const diffMatch =
        activeDifficulty === "all" ||
        pack.categories.some((c) => c.difficulty.includes(activeDifficulty));
      return tagMatch && diffMatch;
    });
  }, [packs, activeTag, activeDifficulty]);

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="packs-layout">
      {/* Filter Sidebar */}
      <aside className="packs-sidebar">
        <div className="packs-filter-section">
          <h4 className="packs-filter-title">Categories</h4>
          <div className="packs-filter-chips">
            {ALL_TAGS.map((tag) => (
              <button
                key={tag}
                onClick={() => setActiveTag(tag)}
                className={`packs-filter-chip ${activeTag === tag ? "packs-filter-chip-active" : ""}`}
              >
                {tag === "all" ? "All Packs" : tag.replace(/-/g, " ")}
              </button>
            ))}
          </div>
        </div>
        <div className="packs-filter-section">
          <h4 className="packs-filter-title">Difficulty</h4>
          <div className="packs-filter-chips">
            {DIFFICULTIES.map((d) => (
              <button
                key={d}
                onClick={() => setActiveDifficulty(d)}
                className={`packs-filter-chip ${activeDifficulty === d ? "packs-filter-chip-active" : ""}`}
              >
                {d === "all" ? "All" : d.charAt(0).toUpperCase() + d.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div className="packs-filter-count">
          <span className="mono-data">{filtered.length}</span> pack
          {filtered.length !== 1 ? "s" : ""} found
        </div>
      </aside>

      {/* Pack Cards */}
      <section className="packs-content">
        {filtered.length === 0 ? (
          <div className="empty-state">
            <p>No packs match the selected filters.</p>
          </div>
        ) : (
          filtered.map((pack) => {
            const isExpanded = expandedId === pack.name;
            const totalSkills = pack.skills.length;

            return (
              <div
                key={pack.name}
                className={`pack-card ${isExpanded ? "pack-card-expanded" : ""}`}
              >
                <div
                  className="pack-card-header"
                  onClick={() => toggleExpand(pack.name)}
                >
                  <div className="pack-card-main">
                    <div className="pack-card-title-row">
                      <h3 className="pack-card-name">{pack.name}</h3>
                      <span className="pack-card-version chip chip-primary">
                        v{pack.version}
                      </span>
                    </div>
                    <p className="pack-card-desc">{pack.description}</p>
                    <div className="pack-card-stats">
                      <span className="pack-stat">
                        <span className="material-symbols-outlined pack-stat-icon">
                          description
                        </span>
                        <span className="pack-stat-value">
                          {pack.total_prompts} prompts
                        </span>
                      </span>
                      <span className="pack-stat">
                        <span className="material-symbols-outlined pack-stat-icon">
                          construction
                        </span>
                        <span className="pack-stat-value">
                          {totalSkills} skills
                        </span>
                      </span>
                      <span className="pack-stat">
                        <span className="material-symbols-outlined pack-stat-icon">
                          category
                        </span>
                        <span className="pack-stat-value">
                          {pack.categories.length} categories
                        </span>
                      </span>
                    </div>
                    <div className="pack-card-tags">
                      {pack.tags.map((tag) => (
                        <span key={tag} className="pack-tag">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                  <span
                    className={`material-symbols-outlined pack-expand-icon ${isExpanded ? "pack-expand-open" : ""}`}
                  >
                    expand_more
                  </span>
                </div>

                {isExpanded && (
                  <div className="pack-card-body animate-entrance">
                    {/* Categories */}
                    <div className="pack-section">
                      <h4 className="pack-section-title">Categories</h4>
                      <div className="pack-categories-grid">
                        {pack.categories.map((cat) => (
                          <div key={cat.id} className="pack-category-item">
                            <div className="pack-cat-header">
                              <span className="pack-cat-label">
                                {cat.label}
                              </span>
                              <span className="pack-cat-count mono-data">
                                {cat.count}
                              </span>
                            </div>
                            <div className="pack-cat-diffs">
                              {cat.difficulty.map((d) => (
                                <span
                                  key={d}
                                  className={`pack-diff-badge pack-diff-${d}`}
                                >
                                  {d}
                                </span>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Skills */}
                    <div className="pack-section">
                      <h4 className="pack-section-title">Available Skills</h4>
                      <div className="pack-skills-list">
                        {pack.skills.map((skill) => (
                          <div key={skill.name} className="pack-skill-item">
                            <code className="pack-skill-name">
                              {skill.name}
                            </code>
                            {skill.version && (
                              <span className="pack-skill-version chip chip-primary">
                                v{skill.version}
                              </span>
                            )}
                            <span className="pack-skill-desc">
                              {skill.description}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Metadata */}
                    {(pack.author || pack.license) && (
                      <div className="pack-meta-row">
                        {pack.author && (
                          <span className="pack-meta-item">
                            👤 {pack.author}
                          </span>
                        )}
                        {pack.license && (
                          <span className="pack-meta-item">
                            📄 {pack.license}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </section>
    </div>
  );
}
