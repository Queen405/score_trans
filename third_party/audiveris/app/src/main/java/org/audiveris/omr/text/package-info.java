/**
 * Package for handling textual aspects in glyphs.
 * <p>
 * <img src="doc-files/Text.png" alt="Text data model">
 * <h2>Detection of text items</h2>
 * <p>
 * The TEXTS step retains text-model and serialized-step compatibility, but does not perform text
 * recognition. Ordinary text extraction is handled by the Score Trans Python backend.
 * <h3>Detection of text-shaped glyphs (NOTA: THIS IS OBSOLETE!)</h3>
 * <p>
 * Later, in SYMBOLS step, some glyphs might be recognized as TEXT shaped glyphs (or have been
 * manually assigned the TEXT shape).
 * Such text is not automatically recognized by this OMR build.
 */
package org.audiveris.omr.text;
