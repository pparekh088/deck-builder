# PowerPoint AI Generator - Demo Script

This demo script walks through the key features and user journey of the PowerPoint AI Generator application.

## Demo Setup

### Prerequisites
1. Ensure both backend and frontend are running
2. Have a sample PowerPoint template ready (.pptx file)
3. Azure OpenAI credentials configured

### Starting the Services

```bash
# Terminal 1 - Backend
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --reload

# Terminal 2 - Frontend
cd frontend
npm run dev
```

## Demo Walkthrough

### 1. Initial Application Load

**Action:** Open browser to `http://localhost:5173`

**What to Show:**
- Clean, modern interface with chat panel and preview panel
- Automatic session creation (note session ID in header)
- WebSocket connection indicator (green "Connected" status)
- Empty state with helpful prompts

**Talking Points:**
- "The application automatically creates a new session when you open it"
- "Real-time connection is established immediately for live updates"
- "Split-screen design allows you to chat and see results simultaneously"

### 2. Template Upload

**Action:** Click on "Upload PowerPoint template" area

**What to Show:**
- Drag-and-drop interface for template upload
- Select a corporate template with branded colors/fonts
- Template name appears in the header after upload
- System message confirms successful upload

**Talking Points:**
- "Users can upload their own branded templates"
- "The template will be used for all slides in this session"
- "Templates ensure consistent branding across generated presentations"

### 3. Creating Initial Presentation

**Action:** Type and send the following message:
```
Create a presentation about "Digital Transformation in 2024" with 5 slides:
1. Title slide
2. What is Digital Transformation?
3. Key Technologies
4. Benefits for Business
5. Conclusion and Next Steps
```

**What to Show:**
- Message appears in chat
- Loading indicator shows AI is processing
- AI response with confirmation
- Preview panel updates with generated slides
- Each slide shows title and bullet points

**Talking Points:**
- "The AI understands complex requests and structures"
- "Content is generated based on the latest GPT-4.1 model"
- "Preview updates in real-time via WebSocket"
- "The template styling is automatically applied"

### 4. Refining Content

**Action:** Send follow-up message:
```
Add more detail to the Key Technologies slide. Include AI, Cloud Computing, and IoT with specific examples.
```

**What to Show:**
- AI understands context from previous messages
- Specific slide is updated with new content
- Preview refreshes automatically
- Slide count and structure maintained

**Talking Points:**
- "The system maintains conversation context"
- "You can refine specific slides without starting over"
- "Changes are incremental and preserve existing work"

### 5. Preview Features

**Action:** Click on individual slides in the preview panel

**What to Show:**
- Slide detail modal opens
- Full content is visible
- Slide numbers and titles clearly shown
- Close modal to return to grid view

**Talking Points:**
- "Each slide can be examined in detail"
- "Content is formatted for PowerPoint compatibility"
- "Preview helps verify content before download"

### 6. Adding New Slides

**Action:** Send message:
```
Add a new slide after Key Technologies about "Implementation Roadmap" with quarterly milestones
```

**What to Show:**
- New slide appears in preview
- Slide numbers automatically adjust
- Content flows naturally

**Talking Points:**
- "Dynamically add slides at any point"
- "AI maintains logical flow and structure"
- "No limit on presentation length"

### 7. Template Change (Optional)

**Action:** Click the paperclip icon next to message input

**What to Show:**
- Template change modal appears
- Upload a different template
- All existing content transfers to new template
- Preview updates with new styling

**Talking Points:**
- "Switch templates without losing content"
- "Useful for trying different visual styles"
- "Template change applies to entire presentation"

### 8. Download Final Presentation

**Action:** Click "Download" button in preview panel

**What to Show:**
- Download starts immediately
- .pptx file saves to downloads folder
- Open file in PowerPoint to show it works

**Talking Points:**
- "One-click download of completed presentation"
- "Standard PowerPoint format - fully editable"
- "All formatting and template styles preserved"

### 9. Advanced Features Demo

**Action:** Show various prompt examples:

```
Make the title slide more impactful with a compelling subtitle
```

```
Add speaker notes to the Benefits slide
```

```
Create a chart slide showing adoption rates
```

**What to Show:**
- AI's ability to understand different request types
- Flexibility in content generation
- Professional output quality

### 10. Session Management

**Action:** Click "New Session" button

**What to Show:**
- Confirmation dialog
- Session reset
- Clean slate for new presentation
- Previous session data cleared

**Talking Points:**
- "Start fresh anytime with a new session"
- "Sessions are isolated for privacy"
- "Each session maintains its own context"

## Key Features to Emphasize

1. **Speed**: From idea to presentation in minutes
2. **Quality**: Professional content powered by GPT-4.1
3. **Customization**: Use your own templates
4. **Iteration**: Refine until perfect
5. **Real-time**: See changes instantly
6. **Simplicity**: Natural language interface

## Common Questions & Answers

**Q: Can I edit the PowerPoint after downloading?**
A: Yes, the downloaded file is a standard .pptx that can be edited in PowerPoint, Google Slides, or any compatible software.

**Q: How many slides can I create?**
A: There's no hard limit. The system can handle presentations with 50+ slides.

**Q: Can I use this offline?**
A: No, the application requires internet connection for AI processing.

**Q: Is my data secure?**
A: Sessions are isolated and can be deleted. No data is permanently stored after session ends.

**Q: Can multiple people work on the same presentation?**
A: Currently, each session is individual. Collaboration features could be added in future versions.

## Troubleshooting During Demo

### If WebSocket disconnects:
- Refresh the page
- Check backend is still running
- New session will be created automatically

### If template upload fails:
- Check file is .pptx format
- Ensure file size is under 10MB
- Try a different template

### If AI responses are slow:
- Check Azure OpenAI service status
- Verify API credentials
- Consider API rate limits

## Demo Conclusion

**Summary Points:**
- Revolutionary way to create presentations
- Saves hours of manual work
- Maintains professional quality
- Fully customizable with templates
- Export to standard formats

**Call to Action:**
- "Ready to transform your presentation workflow?"
- "Let's discuss how this can be integrated into your organization"
- "Questions about specific use cases?"

## Additional Demo Scenarios

### Scenario 1: Sales Pitch
```
Create a sales presentation for our new CRM software targeting enterprise clients. Include ROI data, features, and customer testimonials.
```

### Scenario 2: Educational Content
```
Create an educational presentation about climate change for high school students. Make it engaging with facts and actionable steps.
```

### Scenario 3: Technical Documentation
```
Create a technical presentation about our API architecture including endpoints, authentication, and code examples.
```

### Scenario 4: Company Update
```
Create a quarterly business review presentation with sections for financials, achievements, challenges, and next quarter goals.
```

## Tips for Effective Demos

1. **Prepare templates** beforehand that match the audience's brand
2. **Have backup prompts** ready in case of creative blocks
3. **Show the speed** by timing the generation process
4. **Open the downloaded file** to prove it works
5. **Demonstrate error recovery** to show robustness
6. **Customize examples** to the audience's industry
7. **Keep energy high** - this is exciting technology!

## Metrics to Highlight

- Generation time: ~5-10 seconds per request
- Average presentation creation: 5-10 minutes
- Time saved vs. manual creation: 80-90%
- Number of revisions possible: Unlimited
- Template compatibility: 100% with .pptx format

---

*This demo script should take approximately 15-20 minutes to complete. Adjust based on audience interest and time constraints.*