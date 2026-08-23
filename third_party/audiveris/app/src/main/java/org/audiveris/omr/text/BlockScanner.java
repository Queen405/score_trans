//------------------------------------------------------------------------------------------------//
//                                                                                                //
//                                     B l o c k S c a n n e r                                    //
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
import org.audiveris.omr.util.Navigable;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;

import ij.process.ByteProcessor;

/**
 * Class <code>BlockScanner</code> preserves the text-region API used by manual editing code.
 * <p>
 * Automatic text recognition is provided by the Score Trans Python backend.
 * <p>
 * Any returned text lines are processed at system level by dedicated TextBuilder instances.
 *
 * @author Hervé Bitteur
 */
public class BlockScanner
{
    //~ Static fields/initializers -----------------------------------------------------------------

    private static final Logger logger = LoggerFactory.getLogger(BlockScanner.class);

    //~ Instance fields ----------------------------------------------------------------------------

    /** Related sheet. */
    @Navigable(false)
    private final Sheet sheet;

    //~ Constructors -------------------------------------------------------------------------------

    /**
     * Creates a new <code>GlyphScanner</code> object that can work on a glyph or a buffer.
     *
     * @param sheet underlying sheet
     */
    public BlockScanner (Sheet sheet)
    {
        this.sheet = sheet;
    }

    //~ Methods ------------------------------------------------------------------------------------

    //------------//
    // scanBuffer //
    //------------//
    /**
     * Launch the OCR on the provided buffer, to retrieve the TextLine instance(s) with
     * coordinates <b>relative</b> to buffer origin.
     *
     * @param buffer   the ByteProcessor buffer
     * @param language the probable language spec
     * @param id       an arbitrary id, used only when keeping the image on disk
     * @return a list, not null but perhaps empty, of raw TextLine's with relative coordinates.
     */
    public List<TextLine> scanBuffer (ByteProcessor buffer,
                                      String language,
                                      int id)
    {
        return OcrUtil.scan(
                buffer.getBufferedImage(),
                OCR.LayoutMode.SINGLE_BLOCK,
                language,
                sheet,
                sheet.getId() + "/glyph-" + id);
    }
}
