//------------------------------------------------------------------------------------------------//
//                                                                                                //
//                                          O c r U t i l                                         //
//                                                                                                //
//------------------------------------------------------------------------------------------------//
// <editor-fold defaultstate="collapsed" desc="hdr">
//
//  Copyright © Audiveris 2026. All rights reserved.
//
//  This program is free software: you can redistribute it and/or modify it under the terms of the
//  GNU Affero General Public License as published by the Free Software Foundation, either version
//  3 of the License, or (at your option) any later version.
//
//  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
//  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
//  See the GNU Affero General Public License for more details.
//
//  You should have received a copy of the GNU Affero General Public License along with this
//  program.  If not, see <http://www.gnu.org/licenses/>.
//------------------------------------------------------------------------------------------------//
// </editor-fold>
package org.audiveris.omr.text;

import org.audiveris.omr.sheet.Sheet;

import java.awt.Point;
import java.awt.image.BufferedImage;
import java.util.Collections;
import java.util.List;
import java.util.SortedSet;

/** Compatibility facade for the optional text-recognition integration. */
public abstract class OcrUtil
{
    private static final OCR OCR = new OCR()
    {
        @Override
        public SortedSet<String> getSupportedLanguages ()
        {
            return Collections.emptySortedSet();
        }

        @Override
        public double getMinConfidence ()
        {
            return 0.0;
        }

        @Override
        public String identify ()
        {
            return "Unavailable";
        }

        @Override
        public boolean isAvailable ()
        {
            return false;
        }

        @Override
        public List<TextLine> recognize (Sheet sheet,
                                         BufferedImage image,
                                         Point topLeft,
                                         String langSpec,
                                         OCR.LayoutMode layoutMode,
                                         String label)
        {
            return Collections.emptyList();
        }

        @Override
        public boolean supports (String langSpec)
        {
            return false;
        }
    };

    private OcrUtil ()
    {
    }

    /** Return the disabled compatibility provider. */
    public static OCR getOcr ()
    {
        return OCR;
    }

    /** Return no text lines; ordinary text OCR is provided by the Python backend. */
    public static List<TextLine> scan (BufferedImage image,
                                       OCR.LayoutMode layoutMode,
                                       String languages,
                                       Sheet sheet,
                                       String label)
    {
        return Collections.emptyList();
    }
}
