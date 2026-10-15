# Knowledge base

## Data status

The FAQ examples in `faqs.json` are explicitly illustrative. They are not SNJB policies, placement statistics, recruiter information, or company requirements. No placement-specific institutional information has been verified for this starter project. Confirm official answers through an authorised SNJB placement-cell channel.

The official SNJB website ([snjb.org](https://www.snjb.org/)) was checked while creating this project. It provides general institutional information, but this project did not find placement-specific policies or notices there.

## Adding approved documents

1. Obtain an official placement notice, policy, or company document that is approved for student-facing use.
2. Put the authorised `.txt`, `.md`, or text-readable `.pdf` in `verified_college_information/`.
3. Confirm its accuracy, date, audience, and permission to use it. The folder itself does not make a document verified.
4. Restart the Flask app so it loads the new document.
5. Test representative questions and check that the source filename is returned.
6. Remove superseded documents after confirming the replacement and retaining records according to college policy.

Only retrieved matching passages are sent to Gemini. Unrelated files and all student personal records must stay out of the knowledge base. This starter app has no public document upload or staff administration endpoint.

## File support and limits

`.txt`, `.md`, and `.pdf` documents are read locally at app startup. Documents over 2 MB are ignored, passages are chunked, and up to three matching passages are included in a chat request. Scanned PDFs without extractable text will not be searchable.

Use only authorised information. Do not add private student records, confidential correspondence, or material that is not approved for processing by the configured AI service.
