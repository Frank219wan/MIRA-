import test from 'node:test';
import assert from 'node:assert/strict';
import { isPhotoSelectionCurrent } from '../src/services/localAppearance.ts';
import { toSpecialAreaProfile } from '../src/services/specialAreaService.ts';

test('illustration and older photos are never current photo bindings',()=>{
 const base={region:'局部区域',preference:'integrate',integrateStyle:'natural'};
 assert.equal(isPhotoSelectionCurrent({...base,imageSource:'illustration'},'one'),false);
 assert.equal(isPhotoSelectionCurrent({...base,imageSource:'user-photo',imageId:'old'},'one'),false);
 assert.equal(isPhotoSelectionCurrent({...base,imageSource:'user-photo',imageId:'one'},'one'),true);
 for(const integrateStyle of ['natural','highlight']) {
  const area=toSpecialAreaProfile([{...base,integrateStyle,selection:{x:.5,y:.5,width:.2,height:.2}}]).areas[0];
  assert.equal(area.preference,'HIGHLIGHT');
 }
});
