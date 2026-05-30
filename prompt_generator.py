#!/usr/bin/env python3
"""
Auto-generated prompt system for diverse, non-overfitting benchmarks
Includes real-world debugging scenarios and category-specific generation
"""

import random
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class PromptCategory(Enum):
    """Benchmark prompt categories."""
    CODE = "code"
    FRONTEND = "frontend"
    REASONING = "reasoning"
    MATH = "math"
    INSTRUCTION = "instruction"
    DEBUGGING = "debugging"  # NEW: Real-world debugging scenarios


@dataclass
class GeneratedPrompt:
    """Auto-generated prompt with metadata."""
    category: PromptCategory
    prompt: str
    expected_keywords: List[str]
    constraints: Optional[Dict[str, any]] = None
    expected_answer: Optional[float] = None
    json_schema: Optional[Dict[str, any]] = None
    difficulty: str = "medium"  # easy, medium, hard


class DebuggingScenarioGenerator:
    """Generate real-world debugging scenarios for TypeScript/NestJS/React."""
    
    SCENARIOS = {
        "race_condition": [
            {
                "code": """
// Cache layer with race condition
class CacheService {
  private cache = new Map<string, any>();
  
  async get(key: string): Promise<any> {
    if (this.cache.has(key)) {
      return this.cache.get(key);
    }
    const value = await this.fetchFromDB(key);
    this.cache.set(key, value);
    return value;
  }
  
  private async fetchFromDB(key: string): Promise<any> {
    // Simulate DB call
    return { data: key };
  }
}
""",
                "issue": "Race condition when multiple concurrent requests for same key",
                "expected_fix": ["Promise", "Promise.allSettled", "mutex", "lock", "concurrent", "race"]
            },
            {
                "code": """
// Async state update in React
function UserProfile() {
  const [user, setUser] = useState(null);
  
  useEffect(() => {
    fetchUser().then(data => setUser(data));
    fetchPosts().then(posts => setPosts(posts));
  }, []);
  
  return <div>{user?.name}</div>;
}
""",
                "issue": "Stale closure - user might be null when posts arrive",
                "expected_fix": ["useEffect", "dependency", "cleanup", "abort", "stale", "closure"]
            }
        ],
        "di_bug": [
            {
                "code": """
// NestJS module with incorrect DI
@Module({
  imports: [HttpModule],
  providers: [UserService],
  controllers: [UserController]
})
export class UserModule {
  constructor(private userService: UserService) {}
}

@Controller('users')
export class UserController {
  constructor(private userService: UserService) {}
}
""",
                "issue": "UserService not properly injected in controller",
                "expected_fix": ["@Injectable", "constructor", "provider", "inject", "module"]
            },
            {
                "code": """
// Circular dependency in NestJS
@Injectable()
export class ServiceA {
  constructor(private serviceB: ServiceB) {}
}

@Injectable()
export class ServiceB {
  constructor(private serviceA: ServiceA) {}
}
""",
                "issue": "Circular dependency between services",
                "expected_fix": ["forwardRef", "circular", "dependency", "inject", "module"]
            }
        ],
        "stale_closure": [
            {
                "code": """
// React stale closure with setInterval
function Counter() {
  const [count, setCount] = useState(0);
  
  useEffect(() => {
    const interval = setInterval(() => {
      console.log(count); // Always logs 0
    }, 1000);
    return () => clearInterval(interval);
  }, []);
  
  return <button onClick={() => setCount(c => c + 1)}>Increment</button>;
}
""",
                "issue": "Stale closure - count never updates in interval",
                "expected_fix": ["useRef", "functional", "update", "stale", "closure", "dependency"]
            },
            {
                "code": """
// Event handler with stale state
function Form() {
  const [value, setValue] = useState('');
  
  const handleSubmit = () => {
    console.log(value); // Might be stale
  };
  
  return <input onChange={e => setValue(e.target.value)} onClick={handleSubmit} />;
}
""",
                "issue": "Event handler captures stale state",
                "expected_fix": ["useCallback", "dependency", "functional", "setState", "stale"]
            }
        ],
        "prisma_relation": [
            {
                "code": """
// Prisma relation mismatch
const user = await prisma.user.findUnique({
  where: { id: userId },
  include: { posts: true }
});

// Later
await prisma.post.create({
  data: {
    title: 'New Post',
    author: { connect: { id: user.id } }
  }
});
""",
                "issue": "Relation might not exist or be incorrect",
                "expected_fix": ["relation", "connect", "foreign", "key", "prisma", "schema"]
            },
            {
                "code": """
// Prisma transaction issue
await prisma.$transaction([
  prisma.user.delete({ where: { id } }),
  prisma.post.deleteMany({ where: { userId: id } })
]);
""",
                "issue": "Wrong order - posts should be deleted before user",
                "expected_fix": ["transaction", "order", "foreign", "key", "constraint", "cascade"]
            }
        ],
        "typescript_type_error": [
            {
                "code": """
// Type error with generic function
function processData<T>(data: T): T {
  return data.toUpperCase(); // Error: toUpperCase doesn't exist on T
}
""",
                "issue": "Generic constraint missing",
                "expected_fix": ["generic", "constraint", "extends", "string", "type"]
            },
            {
                "code": """
// Type narrowing issue
function processValue(value: string | number) {
  if (typeof value === 'string') {
    return value.length;
  }
  return value.toFixed(2); // Error: toFixed doesn't exist on number
}
""",
                "issue": "Type narrowing not working correctly",
                "expected_fix": ["type", "narrowing", "typeof", "guard", "interface"]
            }
        ]
    }
    
    def generate_debugging_prompt(self) -> GeneratedPrompt:
        """Generate a real-world debugging scenario."""
        scenario_type = random.choice(list(self.SCENARIOS.keys()))
        scenario = random.choice(self.SCENARIOS[scenario_type])
        
        prompt = f"""
Debug this TypeScript/NestJS/React code:

```typescript
{scenario['code']}
```

**Issue**: {scenario['issue']}

Explain:
1. What's causing the bug
2. Why it happens
3. How to fix it with code

Provide a complete, working solution.
"""
        
        return GeneratedPrompt(
            category=PromptCategory.DEBUGGING,
            prompt=prompt,
            expected_keywords=scenario['expected_fix'],
            difficulty="hard"
        )


class CodePromptGenerator:
    """Generate TypeScript/NestJS coding prompts."""
    
    NESTJS_PATTERNS = [
        "AuthGuard with JWT validation",
        "Custom decorator with metadata reflection",
        "Interceptor for logging and timing",
        "Pipe for validation with class-validator",
        "Guard with role-based access control",
        "Exception filter with custom error responses",
        "Module with dynamic configuration",
        "Service with caching layer",
        "Controller with pagination",
        "WebSocket gateway with authentication"
    ]
    
    REACT_PATTERNS = [
        "Custom hook for data fetching with caching",
        "Higher-order component for authentication",
        "Context provider with TypeScript",
        "Render prop pattern with generics",
        "Compound component pattern",
        "Controlled component with complex state",
        "Form validation with React Hook Form",
        "Suspense boundary with error handling",
        "Virtual scroll with React Window",
        "Animation with Framer Motion"
    ]
    
    TYPESCRIPT_PATTERNS = [
        "Generic utility type",
        "Conditional type with inference",
        "Mapped type with readonly",
        "Template literal type",
        "Recursive type definition",
        "Brand type for nominal typing",
        "Type guard with predicate",
        "Discriminated union",
        "Intersection type",
        "Utility type combination"
    ]
    
    def generate_code_prompt(self) -> GeneratedPrompt:
        """Generate a TypeScript/NestJS/React coding prompt."""
        pattern_type = random.choice(["nestjs", "react", "typescript"])
        
        if pattern_type == "nestjs":
            pattern = random.choice(self.NESTJS_PATTERNS)
            prompt = f"""
Implement a NestJS {pattern}.

Requirements:
- Use proper TypeScript types
- Include error handling
- Follow NestJS best practices
- Add necessary decorators
- Include example usage

Provide complete, working code with imports.
"""
            keywords = ["@Injectable", "@Controller", "@Module", "constructor", "decorator"]
        
        elif pattern_type == "react":
            pattern = random.choice(self.REACT_PATTERNS)
            prompt = f"""
Create a React {pattern}.

Requirements:
- Use TypeScript with proper types
- Include proper hooks usage
- Handle edge cases
- Add loading/error states
- Include example usage

Provide complete, working code with imports.
"""
            keywords = ["useState", "useEffect", "interface", "type", "React"]
        
        else:  # typescript
            pattern = random.choice(self.TYPESCRIPT_PATTERNS)
            prompt = f"""
Implement a TypeScript {pattern}.

Requirements:
- Use advanced TypeScript features
- Include proper type constraints
- Add type guards where needed
- Include usage examples
- Explain the type logic

Provide complete, working code with examples.
"""
            keywords = ["type", "interface", "generic", "extends", "infer"]
        
        return GeneratedPrompt(
            category=PromptCategory.CODE,
            prompt=prompt,
            expected_keywords=keywords,
            difficulty=random.choice(["easy", "medium", "hard"])
        )


class FrontendPromptGenerator:
    """Generate frontend/UI prompts."""
    
    PATTERNS = [
        "Hero section with parallax effect",
        "Card grid with hover animations",
        "Modal with backdrop blur",
        "Navigation with mobile menu",
        "Form with validation and feedback",
        "Dashboard with charts",
        "Loading skeleton with shimmer",
        "Infinite scroll with virtualization",
        "Drag and drop list",
        "Image gallery with lightbox"
    ]
    
    TECH_STACKS = [
        "React + Tailwind CSS + Framer Motion",
        "React + CSS Modules + React Spring",
        "React + Styled Components + Framer Motion",
        "React + Tailwind CSS + GSAP",
        "React + Emotion + Framer Motion"
    ]
    
    def generate_frontend_prompt(self) -> GeneratedPrompt:
        """Generate a frontend/UI prompt."""
        pattern = random.choice(self.PATTERNS)
        tech_stack = random.choice(self.TECH_STACKS)
        
        prompt = f"""
Build a {pattern} using {tech_stack}.

Requirements:
- Responsive design
- Smooth animations
- Proper accessibility (ARIA)
- Mobile-first approach
- Clean, modern aesthetics

Provide complete, working code with all necessary components and styles.
"""
        
        keywords = ["component", "responsive", "animation", "accessibility", "style"]
        
        return GeneratedPrompt(
            category=PromptCategory.FRONTEND,
            prompt=prompt,
            expected_keywords=keywords,
            difficulty=random.choice(["easy", "medium", "hard"])
        )


class ReasoningPromptGenerator:
    """Generate architecture and system design prompts."""
    
    ARCHITECTURE_PATTERNS = [
        "Real-time collaborative document editor",
        "E-commerce microservices platform",
        "Social media feed with caching",
        "Chat application with WebSocket",
        "File storage system with CDN",
        "API gateway with rate limiting",
        "Event-driven notification system",
        "Multi-tenant SaaS application",
        "GraphQL API with federation",
        "CQRS pattern with event sourcing"
    ]
    
    def generate_reasoning_prompt(self) -> GeneratedPrompt:
        """Generate an architecture reasoning prompt."""
        pattern = random.choice(self.ARCHITECTURE_PATTERNS)
        
        prompt = f"""
Design the architecture for a {pattern}.

Consider:
- Scalability and performance
- Data consistency and transactions
- Caching strategies
- Error handling and resilience
- Security considerations
- Technology choices

Provide:
1. High-level architecture diagram (text description)
2. Key components and their responsibilities
3. Data flow between components
4. Technology stack justification
5. Potential challenges and mitigations
"""
        
        keywords = ["architecture", "scalability", "component", "data", "flow", "service"]
        
        return GeneratedPrompt(
            category=PromptCategory.REASONING,
            prompt=prompt,
            expected_keywords=keywords,
            difficulty=random.choice(["medium", "hard"])
        )


class MathPromptGenerator:
    """Generate developer-focused math problems."""
    
    def generate_math_prompt(self) -> GeneratedPrompt:
        """Generate a developer-focused math problem."""
        problem_types = [
            {
                "type": "api_rate_limiting",
                "prompt": "An API has a rate limit of 1000 requests per minute. If your application makes 25 requests per second, how long until you hit the limit? What's the maximum sustainable requests per second?",
                "answer": 40.0  # 1000/60 = 16.67 rps max, 25 rps hits in 40s
            },
            {
                "type": "cache_hit_rate",
                "prompt": "A cache has a 70% hit rate. Cache lookups take 1ms, database queries take 100ms. What's the average response time?",
                "answer": 31.0  # 0.7*1 + 0.3*100 = 0.7 + 30 = 30.7ms
            },
            {
                "type": "database_sharding",
                "prompt": "You have 10 million users. Each shard can handle 1 million users. How many shards do you need? If you add 5 million users, how many additional shards?",
                "answer": 5.0  # 10M/1M = 10 shards, 5M/1M = 5 additional
            },
            {
                "type": "pagination_calculation",
                "prompt": "An API returns 50 items per page. You have 1,247 total items. How many full pages? How many items on the last page?",
                "answer": 24.0  # 1247/50 = 24.94, so 24 full pages, 47 items on last
            },
            {
                "type": "memory_calculation",
                "prompt": "Each user session stores 2KB of data. With 100,000 concurrent users, how much RAM is needed? If you compress to 500B per session?",
                "answer": 200.0  # 100K * 2KB = 200MB, compressed = 50MB
            }
        ]
        
        problem = random.choice(problem_types)
        
        return GeneratedPrompt(
            category=PromptCategory.MATH,
            prompt=problem["prompt"],
            expected_answer=problem["answer"],
            difficulty="medium"
        )


class InstructionPromptGenerator:
    """Generate instruction following prompts."""
    
    CONSTRAINTS = [
        {
            "type": "json_only",
            "prompt": "Describe React in valid JSON only with this structure: {{\"framework\": \"string\", \"version\": \"number\", \"features\": [\"string\"]}}",
            "constraints": {"json_only": True},
            "schema": {"framework": str, "version": (int, float), "features": list}
        },
        {
            "type": "exact_bullets",
            "prompt": "List exactly 3 benefits of using TypeScript. Use bullet points. No markdown formatting.",
            "constraints": {"bullet_count": 3, "no_markdown": True}
        },
        {
            "type": "one_sentence",
            "prompt": "Explain what NestJS is in exactly one sentence. No markdown, no bullet points.",
            "constraints": {"sentence_count": 1, "no_markdown": True}
        },
        {
            "type": "max_length",
            "prompt": "Explain the difference between GET and POST in under 100 characters.",
            "constraints": {"max_length": 100}
        },
        {
            "type": "no_code",
            "prompt": "Explain what a React hook is without using any code examples or code blocks.",
            "constraints": {"no_markdown": True}
        }
    ]
    
    def generate_instruction_prompt(self) -> GeneratedPrompt:
        """Generate an instruction following prompt."""
        constraint = random.choice(self.CONSTRAINTS)
        
        return GeneratedPrompt(
            category=PromptCategory.INSTRUCTION,
            prompt=constraint["prompt"],
            constraints=constraint["constraints"],
            json_schema=constraint.get("schema"),
            difficulty="easy"
        )


class PromptGenerator:
    """Main prompt generator with category-based generation."""
    
    def __init__(self):
        self.debugging_gen = DebuggingScenarioGenerator()
        self.code_gen = CodePromptGenerator()
        self.frontend_gen = FrontendPromptGenerator()
        self.reasoning_gen = ReasoningPromptGenerator()
        self.math_gen = MathPromptGenerator()
        self.instruction_gen = InstructionPromptGenerator()
    
    def generate_prompt(self, category: PromptCategory) -> GeneratedPrompt:
        """Generate a prompt for the specified category."""
        generators = {
            PromptCategory.DEBUGGING: self.debugging_gen.generate_debugging_prompt,
            PromptCategory.CODE: self.code_gen.generate_code_prompt,
            PromptCategory.FRONTEND: self.frontend_gen.generate_frontend_prompt,
            PromptCategory.REASONING: self.reasoning_gen.generate_reasoning_prompt,
            PromptCategory.MATH: self.math_gen.generate_math_prompt,
            PromptCategory.INSTRUCTION: self.instruction_gen.generate_instruction_prompt
        }
        
        generator = generators.get(category)
        if generator:
            return generator()
        else:
            raise ValueError(f"Unknown category: {category}")
    
    def generate_batch(self, 
                      counts: Dict[PromptCategory, int]) -> List[GeneratedPrompt]:
        """Generate a batch of prompts with specified counts per category."""
        prompts = []
        
        for category, count in counts.items():
            for _ in range(count):
                prompts.append(self.generate_prompt(category))
        
        # Shuffle for variety
        random.shuffle(prompts)
        return prompts
    
    def generate_default_batch(self, total_prompts: int = 20) -> List[GeneratedPrompt]:
        """Generate a default batch with category weights."""
        # Weights: Code 40%, Frontend 20%, Reasoning 15%, Math 15%, Instruction 5%, Debugging 5%
        weights = {
            PromptCategory.CODE: 0.40,
            PromptCategory.FRONTEND: 0.20,
            PromptCategory.REASONING: 0.15,
            PromptCategory.MATH: 0.15,
            PromptCategory.INSTRUCTION: 0.05,
            PromptCategory.DEBUGGING: 0.05
        }
        
        counts = {}
        for category, weight in weights.items():
            counts[category] = max(1, int(total_prompts * weight))
        
        return self.generate_batch(counts)


# Convenience function
def generate_prompts(count: int = 20) -> List[GeneratedPrompt]:
    """Generate a batch of diverse prompts."""
    generator = PromptGenerator()
    return generator.generate_default_batch(count)


if __name__ == "__main__":
    # Test generation
    generator = PromptGenerator()
    
    print("=== Debugging Prompt ===")
    debug_prompt = generator.generate_prompt(PromptCategory.DEBUGGING)
    print(debug_prompt.prompt)
    print()
    
    print("=== Code Prompt ===")
    code_prompt = generator.generate_prompt(PromptCategory.CODE)
    print(code_prompt.prompt)
    print()
    
    print("=== Frontend Prompt ===")
    frontend_prompt = generator.generate_prompt(PromptCategory.FRONTEND)
    print(frontend_prompt.prompt)
    print()
    
    print("=== Reasoning Prompt ===")
    reasoning_prompt = generator.generate_prompt(PromptCategory.REASONING)
    print(reasoning_prompt.prompt)
    print()
    
    print("=== Math Prompt ===")
    math_prompt = generator.generate_prompt(PromptCategory.MATH)
    print(math_prompt.prompt)
    print()
    
    print("=== Instruction Prompt ===")
    instruction_prompt = generator.generate_prompt(PromptCategory.INSTRUCTION)
    print(instruction_prompt.prompt)
